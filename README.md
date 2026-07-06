# SupportAI Platform 

SupportAI is an intelligent customer support platform featuring an **FAQ Chatbot** and a real-time **Voice Assistant**. It utilizes LLMs (Large Language Models) for conversational intelligence, Speech-to-Text (STT) for voice transcription, and Text-to-Speech (TTS) for vocalized responses.

---

## 🌟 Features

- **FAQ Chatbot**: Handles textual support queries, tracks intents, and logs support requests.
- **Voice Assistant**: Allows users to record voice inputs, transcribes speech in real time, and synthesizes natural audio responses.
- **Conversation History**: Displays past interactions, text transcripts, and audio playback for voice logs.
- **Multi-language Support**: Seamless toggle between English, Hindi, Marathi, Tamil, and Telugu.
- **Ticket Edge Theme UI**: Sleek, modern dark-mode interface with micro-interactions and clean styles.

---

## 🛠️ Tech Stack

- **Backend**: FastAPI (Python 3.10+), SQLAlchemy (ORM), SQLite (Database)
- **AI & Voice Services**:
  - LLM: Groq API (llama-3.3-70b-versatile)
  - STT (Speech-to-Text): Groq Whisper transcription API
  - TTS (Text-to-Speech): Edge TTS library (`edge-tts`)
- **Frontend**: Vanilla HTML5, CSS3, JavaScript (ES6+), dynamic translation engine

---

## 📂 Project Structure

```text
support-ai/
├── backend/                  # FastAPI Application
│   ├── app/
│   │   ├── api/routes/       # Auth, User, Booking, Chat, & Conversation API routes
│   │   ├── core/             # Database session & exception handlers
│   │   ├── voice/            # Voice services (STT, TTS pipelines)
│   │   └── database/         # SQLite DB models & schemas
│   ├── temp/                 # Stores user audio uploads (.webm) [Ignored by Git]
│   ├── generated_audio/      # Stores AI response audio (.mp3) [Ignored by Git]
│   ├── main.py               # Main entry point
│   ├── requirements.txt      # Python dependencies
│   └── .env.example          # Template for environment variables
├── frontend/                 # Frontend Static Assets
│   ├── css/                  # Styling (UI design sheets)
│   ├── js/                   # Frontend logic (auth, chat, voice, history)
│   ├── pages/                # Sub-pages (chat.html, voice.html, history.html)
│   ├── index.html            # Main Landing / Login page
│   └── dashboard.html        # Main Dashboard page
└── README.md                 # Project documentation
```

---

##  Installation & Setup

### 1. Clone the Repository
```bash
git clone <your-repo-url>
cd support-ai
```

### 2. Configure Backend Environment Variables
Navigate to the `backend/` directory, copy the example environment file, and fill in your keys:
```bash
cd backend
cp .env.example .env
```
Open `.env` and configure your settings:
- **`GROQ_API_KEY`**: Your Groq Console API Key (for LLM and Whisper STT).
- **`SECRET_KEY`**: A secure string for session hashing.

> [!IMPORTANT]
> The `.env` file contains sensitive credentials and is automatically ignored by Git (configured in `.gitignore`). **Never commit your `.env` file to version control.**

### 3. Setup Python Virtual Environment & Install Dependencies
```bash
python -m venv venv
# On Windows (PowerShell/CMD)
.\venv\Scripts\activate
# On Linux/macOS
source venv/bin/activate

pip install -r requirements.txt
```

---

## 🏃 Running the Application

### Start the Backend Server
Make sure your virtual environment is active in the `backend/` folder and run:
```bash
uvicorn main:app --port 8000 --reload
```
- The backend will start on **`http://127.0.0.1:8000`**.
- Interactive API documentation will be available at **`http://127.0.0.1:8000/docs`**.

### Start the Frontend Server
Because the frontend communicates with the FastAPI server via Javascript modules, it needs to be served via an HTTP server. Run a local server from the **`frontend/`** directory:

**Using Python:**
```bash
cd ../frontend
python -m http.server 5500
```
- Access the web interface at **`http://localhost:5500`**.

**Using VS Code:**
- Install the **Live Server** extension.
- Right-click `index.html` inside the `frontend/` folder and select **Open with Live Server**.

---

## 🔒 Security & Git Ignore

To keep API keys, local databases, and temporary audio assets private, the following patterns are tracked in the root `.gitignore`:
- **Secrets**: `.env` (contains API keys)
- **Local Databases**: `*.db`, `*.sqlite`
- **Temp Directories**: `backend/temp/` (voice recordings) and `backend/generated_audio/` (synthesized voice responses)
- **Python Artifacts**: `__pycache__/`, `venv/`
