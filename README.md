# Callbox Assistant (Callie)

**Callie** is a next-generation AI assistant platform designed to orchestrate digital workforces. It combines advanced reasoning capabilities (Gemini 3 Pro) with enterprise data integration (Google BigQuery) and a seamless, multi-agent chat interface.

![Callie UI](./ui/public/Callie-ui-preview.png) *(Note: Add a screenshot here if available)*

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

## 📦 Installation & Docker Setup

### 🐳 Docker (Recommended)
You can run the entire application stack using Docker Compose.

1. **Clone the Repository**
   ```bash
   git clone git@github.com:dudezki/cbs-agent.git
   cd cbs-agent
   ```

2. **Run with Docker Compose**
   ```bash
   docker-compose up --build
   ```
   - **UI**: [http://localhost:5173](http://localhost:5173)
   - **API**: [http://localhost:8000](http://localhost:8000)

---

### 💻 Local Development (Manual)

#### 1. Backend Setup
The backend code is now located in the `api/` directory.

```bash
cd api

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env
echo "GOOGLE_API_KEY=your_key" > .env
... (add other keys)

# Run Backend
python main.py
```

#### 2. Frontend Setup
The frontend code is in the `ui/` directory.

```bash
cd ui

# Install dependencies
npm install

# Run Frontend
npm run dev -- --host
```

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
