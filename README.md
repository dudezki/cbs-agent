# Callbox Assistant (Cally)

**Cally** is a next-generation AI assistant platform designed to orchestrate digital workforces. It combines advanced reasoning capabilities (Gemini 3 Pro) with enterprise data integration (Google BigQuery) and a seamless, multi-agent chat interface.

![Cally UI](./ui/public/cally-ui-preview.png) *(Note: Add a screenshot here if available)*

## 🚀 Features

- **Multi-Agent Orchestration**: Interact with specialized agents for data analysis, content creation, and more.
- **Advanced Reasoning**: Powered by Google's **Gemini 3 Pro** (and Flash models for speed) to handle complex tasks.
- **Lazy Session Management**:
  - Sessions are created only upon the first message.
  - **Auto-Titling**: innovative zero-latency title generation using Gemini 2.5 Flash.
  - Persistent chat history via SQLite.
- **Enterprise Security**:
  - Secure **Google Authentication** (OAuth 2.0).
  - Backend token verification.
- **Reactive UI**:
  - Built with **Vue 3** and **Tailwind CSS v4**.
  - Smooth animations using `@vueuse/motion`.
  - Glassmorphism design with transparent headers and rich gradients.
  - **BigQuery Integration**: Directly query and visualize massive datasets.

## 🛠️ Tech Stack

### Backend
- **Framework**: FastAPI (Python 3.14+)
- **AI SDK**: `google-genai`, `google.adk` (Agent Development Kit)
- **Database**: `aiosqlite` (Async SQLite)
- **Auth**: `google-auth`

### Frontend
- **Framework**: Vue 3 (Composition API)
- **Build Tool**: Vite
- **Styling**: Tailwind CSS v4
- **Motion**: `@vueuse/motion`
- **Auth**: `vue3-google-login`

## 📦 Installation

### Prerequisites
- Python 3.12+
- Node.js 18+
- Google Cloud Project with Vertex AI and OAuth configured.

### 1. Clone the Repository
```bash
git clone git@github.com:dudezki/cbs-agent.git
cd cbs-agent
```

### 2. Backend Setup
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

**Configuration**:
Create a `.env` file in the root:
```env
GOOGLE_API_KEY=your_gemini_api_key
GOOGLE_CLIENT_ID=your_oauth_client_id
GOOGLE_CLIENT_SECRET=your_oauth_client_secret
```

### 3. Frontend Setup
```bash
cd ui

# Install dependencies
npm install

# Configure Environment
echo "VITE_GOOGLE_CLIENT_ID=your_google_client_id" > .env
```

## 🏃‍♂️ Running the Application

### Start Backend
```bash
# In the root directory
./venv/bin/python main.py
```
The server will start at `http://localhost:8000`.

### Start Frontend
```bash
# In the ui directory
npm run dev -- --host
```
The UI will be available at `http://localhost:5173`.

## 🤝 Contributing
1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 👥 Authors & Ownership

**Callbox, Inc.**  
*Cloud & IA Solutions Architect*

- **Lucky John Faderon**
  - Email: [luckyf@callboxinc.com](mailto:luckyf@callboxinc.com)
  - Cloud Email: [cloud@callboxinc.com](mailto:cloud@callboxinc.com)

## 📄 License
Distributed under the MIT License. See `LICENSE` for more information.
Copyright © 2026 Callbox, Inc.
