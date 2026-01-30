
import asyncio
import sys
import os
from google.adk.cli.utils.service_factory import create_session_service_from_options

# Add current directory to path
sys.path.append(os.getcwd())

async def inspect_session():
    try:
        session_service = create_session_service_from_options(base_dir=".", use_local_storage=True)
        # Assuming app_name is 'agent_sm' and user_id is 'user_001' from App.vue
        sessions_list = await session_service.list_sessions(app_name="agent_sm", user_id="user_001")
        
        if sessions_list.sessions:
            first_session = sessions_list.sessions[0]
            print("Session fields:", first_session.model_dump().keys())
            print("Full session dump:", first_session.model_dump())
        else:
            print("No sessions found to inspect.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(inspect_session())
