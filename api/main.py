import logging
import os
from dotenv import load_dotenv

load_dotenv()

# Monkey patch google-adk BEFORE any other imports that might use it
from google.adk.models.google_llm import Gemini

_PATCHED_CLIENTS = {}

def get_vertex_client(project_id, location):
    key = (project_id, location)
    if key not in _PATCHED_CLIENTS:
        from google import genai
        _PATCHED_CLIENTS[key] = genai.Client(
            vertexai=True,
            project=project_id,
            location=location
        )
    return _PATCHED_CLIENTS[key]

@property
def patched_api_client(self):
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "callbox-core")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
    return get_vertex_client(project_id, location)

@property
def patched_live_api_client(self):
    return patched_api_client.fget(self)

Gemini.api_client = patched_api_client
Gemini._live_api_client = patched_live_api_client
Gemini._api_backend = property(lambda self: 'vertex')

import uvicorn
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from google.adk.cli.adk_web_server import AdkWebServer
from google.adk.cli.utils.agent_loader import AgentLoader
from google.adk.cli.utils.service_factory import (
    create_artifact_service_from_options,
    create_memory_service_from_options,
    create_session_service_from_options,
)
from google.adk.cli.service_registry import load_services_module
from google.adk.auth.credential_service.in_memory_credential_service import (
    InMemoryCredentialService,
)
from google.adk.cli.utils.evals import create_gcs_eval_managers_from_uri
from google.adk.evaluation.local_eval_sets_manager import LocalEvalSetsManager
from google.adk.evaluation.local_eval_set_results_manager import LocalEvalSetResultsManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_app(
    agents_dir: str = ".",
    host: str = "0.0.0.0",
    port: int = 8000,
    web_assets_dir: Optional[str] = None,
) -> FastAPI:
    
    # Initialize Eval Managers (Local default)
    eval_sets_manager = LocalEvalSetsManager(agents_dir=agents_dir)
    eval_set_results_manager = LocalEvalSetResultsManager(agents_dir=agents_dir)

    # Initialize Agent Loader
    agent_loader = AgentLoader(agents_dir)
    load_services_module(agents_dir)

    # Build Services
    memory_service = create_memory_service_from_options(base_dir=agents_dir)
    session_service = create_session_service_from_options(
        base_dir=agents_dir,
        use_local_storage=True
    )
    artifact_service = create_artifact_service_from_options(
        base_dir=agents_dir,
        strict_uri=True,
        use_local_storage=True
    )
    credential_service = InMemoryCredentialService()

    # Initialize ADK Web Server
    adk_web_server = AdkWebServer(
        agent_loader=agent_loader,
        session_service=session_service,
        artifact_service=artifact_service,
        memory_service=memory_service,
        credential_service=credential_service,
        eval_sets_manager=eval_sets_manager,
        eval_set_results_manager=eval_set_results_manager,
        agents_dir=agents_dir,
    )

    # Create FastAPI app
    app = adk_web_server.get_fast_api_app(
        web_assets_dir=web_assets_dir,
        allow_origins=["*"], # Allow all for development
    )

    from fastapi import WebSocket, WebSocketDisconnect
    from google.adk.events.event import Event
    from google.adk.agents.run_config import RunConfig, StreamingMode
    from google.adk.utils.context_utils import Aclosing

    from google.genai import types
    from google.oauth2 import id_token
    from google.auth.transport import requests as google_requests
    from pydantic import BaseModel
    from db import init_db, get_agents

    # Initialize agents DB
    init_db()

    class VerifyRequest(BaseModel):
        token: str
        client_id: str

    @app.get("/api/agents")
    async def list_agents():
        return get_agents()

    @app.post("/auth/verify")
    async def verify_token(request: VerifyRequest):
        logger.info(f"Received verification request for client_id: {request.client_id}")
        
        # 1. Try to verify as ID Token (JWT)
        try:
            idinfo = id_token.verify_oauth2_token(
                request.token, 
                google_requests.Request(), 
                request.client_id
            )
            return {
                "user_id": idinfo.get('email'),
                "name": idinfo.get('name'),
                "picture": idinfo.get('picture'),
                "email": idinfo.get('email')
            }
        except ValueError:
            # 2. Fallback: Try to verify as Access Token via UserInfo API
            logger.info("ID token verification failed, trying as Access Token...")
            try:
                import requests
                resp = requests.get(
                    'https://www.googleapis.com/oauth2/v3/userinfo',
                    headers={'Authorization': f'Bearer {request.token}'}
                )
                resp.raise_for_status()
                user_info = resp.json()
                
                # Check if audience/azp matches? Access tokens don't always carry audience in the same way,
                # but fetching from googleapis with it proves it's valid and grants access to that user's profile.
                # We trust Google's response here for the user's identity.
                
                return {
                    "user_id": user_info.get('email'),
                    "name": user_info.get('name'),
                    "picture": user_info.get('picture'),
                    "email": user_info.get('email')
                }
            except Exception as e:
                logger.error(f"Token verification failed: {e}")
                raise HTTPException(status_code=401, detail="Invalid token")

    import asyncio

    @app.websocket("/ui/ws")
    async def ui_websocket(websocket: WebSocket):
        await websocket.accept()
        ws_lock = asyncio.Lock()

        async def send_message(message: dict):
            async with ws_lock:
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    logger.error(f"Error sending message: {e}")

        async def process_chat(app_name, user_id, session_id, new_message_data):
            try:
                # Convert dict to Content object
                if isinstance(new_message_data, dict):
                   new_message = types.Content(**new_message_data)
                else:
                   new_message = new_message_data

                runner = await adk_web_server.get_runner_async(app_name)
                async with Aclosing(
                    runner.run_async(
                        user_id=user_id,
                        session_id=session_id,
                        new_message=new_message,
                        run_config=RunConfig(streaming_mode=StreamingMode.SSE)
                    )
                ) as agen:
                    async for event in agen:
                        await send_message({
                            "type": "agent_event",
                            "session_id": session_id,
                            "event": event.model_dump(mode='json', by_alias=True)
                        })
                
                await send_message({"type": "chat_complete", "session_id": session_id})

                # Post-processing: Generate Title
                current_session = await adk_web_server.session_service.get_session(
                    app_name=app_name, user_id=user_id, session_id=session_id
                )
                
                if current_session and not current_session.state.get("title"):
                     user_msgs = [e for e in current_session.events if e.content and e.content.role == 'user']
                     if user_msgs:
                         topic_text = user_msgs[0].content.parts[0].text
                         from agent_sm.agent import title_agent
                         # Simpler generation using google.genai directly as discussed
                         from google import genai
                         from dotenv import load_dotenv
                         load_dotenv()
                         
                         api_key = os.environ.get("GOOGLE_GEMINI_API_KEY")
                         if api_key:
                             client = genai.Client(api_key=api_key)
                         else:
                             project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "callbox-core")
                             location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
                             client = genai.Client(vertexai=True, project=project_id, location=location)
                         
                         response = client.models.generate_content(
                             model='gemini-2.5-flash', 
                             contents=[
                                types.Content(role="user", parts=[types.Part(text=topic_text)])
                             ],
                             config=types.GenerateContentConfig(
                                 system_instruction=title_agent.instruction
                             )
                         )
                         
                         title = response.text.strip() if response.text else "New Chat"
                         title = title.replace('"', '').replace("'", "")
                         
                         # Update session title using append_event with state_delta
                         from google.adk.events.event import Event
                         from google.adk.events.event_actions import EventActions
                         
                         update_event = Event(
                             author="system",
                             actions=EventActions(state_delta={"title": title})
                         )
                         await adk_web_server.session_service.append_event(current_session, update_event)
                         
                         current_session.state["title"] = title
                         
                         await send_message({
                            "type": "session_updated",
                            "session": current_session.model_dump(mode='json')
                         })

            except Exception as e:
                logger.error(f"Error in chat task: {e}")
                logger.exception("Full traceback:")
                await send_message({"type": "error", "message": str(e), "session_id": session_id})

        try:
            while True:
                data = await websocket.receive_json()
                msg_type = data.get("type")
                
                if msg_type == "create_session":
                    # ... existing code ...
                    app_name = data.get("app_name")
                    user_id = data.get("user_id", "default_user")
                    try:
                        session = await adk_web_server._create_session(
                            app_name=app_name, 
                            user_id=user_id
                        )
                        await send_message({
                            "type": "session_created",
                            "session": session.model_dump(mode='json')
                        })
                    except Exception as e:
                        logger.error(f"Error creating session: {e}")
                        await send_message({"type": "error", "message": str(e)})

                elif msg_type == "list_sessions":
                    app_name = data.get("app_name")
                    user_id = data.get("user_id", "default_user")
                    try:
                        sessions_list = await adk_web_server.session_service.list_sessions(
                            app_name=app_name, user_id=user_id
                        )
                        
                        # Hydrate sessions to ensure we get titles (State)
                        hydrated_sessions = []
                        for s in sessions_list.sessions:
                            try:
                                full_s = await adk_web_server.session_service.get_session(
                                   app_name=app_name, user_id=user_id, session_id=s.id
                                )
                                if full_s:
                                    hydrated_sessions.append(full_s)
                                else:
                                    hydrated_sessions.append(s)
                            except Exception:
                                hydrated_sessions.append(s)

                        sorted_sessions = sorted(
                            hydrated_sessions, 
                            key=lambda s: s.last_update_time if hasattr(s, 'last_update_time') and s.last_update_time else 0, 
                            reverse=True
                        )
                        await send_message({
                            "type": "sessions_list",
                            "sessions": [s.model_dump(mode='json') for s in sorted_sessions]
                        })
                    except Exception as e:
                        logger.error(f"Error listing sessions: {e}")
                        await send_message({"type": "error", "message": str(e)})

                elif msg_type == "delete_session":
                    app_name = data.get("app_name")
                    user_id = data.get("user_id", "default_user")
                    session_id = data.get("session_id")
                    
                    if not session_id:
                        continue

                    try:
                        await adk_web_server.session_service.delete_session(
                            app_name=app_name, user_id=user_id, session_id=session_id
                        )
                        await send_message({
                            "type": "session_deleted",
                            "session_id": session_id
                        })
                    except Exception as e:
                        logger.error(f"Error deleting session: {e}")
                        await send_message({"type": "error", "message": str(e)})

                elif msg_type == "load_history":
                    app_name = data.get("app_name")
                    user_id = data.get("user_id", "default_user")
                    session_id = data.get("session_id")
                    
                    if not session_id:
                        await send_message({"type": "error", "message": "session_id required loading history"})
                        continue
                        
                    try:
                        session = await adk_web_server.session_service.get_session(
                            app_name=app_name, user_id=user_id, session_id=session_id
                        )
                        if session and session.events:
                            for event in session.events:
                                await send_message({
                                    "type": "agent_event",
                                    "session_id": session_id,
                                    "event": event.model_dump(mode='json', by_alias=True)
                                })
                            await send_message({"type": "history_complete", "session_id": session_id})
                        else:
                             await send_message({"type": "history_complete", "session_id": session_id})
                             
                    except Exception as e:
                        logger.error(f"Error loading history: {e}")
                        await send_message({"type": "error", "message": str(e)})

                elif msg_type == "chat":
                    app_name = data.get("app_name")
                    user_id = data.get("user_id", "default_user")
                    session_id = data.get("session_id")
                    new_message_data = data.get("new_message") 
                    
                    # Lazy Session Creation
                    if not session_id or session_id == 'new':
                        try:
                            # 1. Generate Title
                            from google import genai
                            from dotenv import load_dotenv
                            load_dotenv()
                            
                            api_key = os.environ.get("GOOGLE_GEMINI_API_KEY")
                            if api_key:
                                client = genai.Client(api_key=api_key)
                            else:
                                project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "callbox-core")
                                location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
                                client = genai.Client(vertexai=True, project=project_id, location=location)
                             
                            user_text = ""
                            if isinstance(new_message_data, dict):
                                parts = new_message_data.get('parts', [])
                                if parts and 'text' in parts[0]:
                                    user_text = parts[0]['text']
                            
                            # Simple title prompt
                            title_prompt = "Generate a very short, concise title (3-5 words max) for this chat message. Do not use quotes."
                            response = client.models.generate_content(
                                model='gemini-2.5-flash', 
                                contents=[
                                    types.Content(role="user", parts=[types.Part(text=f"Message: {user_text}")])
                                ],
                                config=types.GenerateContentConfig(
                                    system_instruction=title_prompt
                                )
                            )
                            title = response.text.strip() if response.text else "New Chat"
                            title = title.replace('"', '').replace("'", "")
                            
                            # 2. Create Session
                            session = await adk_web_server._create_session(
                                app_name=app_name, 
                                user_id=user_id,
                                state={"title": title}
                            )
                            
                            session_id = session.id
                            
                            # 3. Notify UI immediately
                            await send_message({
                                "type": "session_created",
                                "session": session.model_dump(mode='json')
                            })
                            
                        except Exception as e:
                            logger.error(f"Error creating lazy session: {e}")
                            await send_message({"type": "error", "message": f"Failed to create session: {str(e)}"})
                            continue

                    # Spawn background task
                    asyncio.create_task(process_chat(app_name, user_id, session_id, new_message_data))

        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.error(f"WebSocket error: {e}")

    # Mount static files at root / (last, to avoid covering other routes)
    if web_assets_dir:
        app.mount("/", StaticFiles(directory=web_assets_dir, html=True), name="public")

    return app

if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    ui_dist_dir = os.path.join(current_dir, "ui", "dist")
    
    # Ensure ui dist exists or handle it gracefully? 
    # For now, we assume build steps will happen.
    if not os.path.exists(ui_dist_dir):
        logger.warning(f"UI dist directory not found at {ui_dist_dir}. Serving API only.")
        web_assets = None
    else:
        web_assets = ui_dist_dir

    app = create_app(web_assets_dir=web_assets)
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
