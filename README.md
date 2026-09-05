<div align="center">
  <h1>🌍 RouteWise Agentic</h1>
  <p><strong>An Autonomous Multi-Modal Travel & Transit Coordinator for Tourism in Sri Lanka.</strong></p>
  <p>
    Built for the <b>AI Buildathon 2026</b> (Hospitality & Tourism Track)
  </p>
</div>

<hr />

## 📖 Overview

**RouteWise Agentic** is not just another map or routing app. It is a fully autonomous **Agentic AI** travel coordinator that acts as your personal travel assistant. 

Instead of forcing users to navigate complex booking forms and disconnected transit schedules, RouteWise takes a single natural-language request and autonomously figures out the rest. It *understands* your constraints (budget, luggage, walking preferences), *reasons* over live multi-modal transit options, *acts* by simulating bookings, *adapts* to real-time delays, and *delivers* a complete travel itinerary and digital boarding pass.

> **The Golden Scenario:**
> *"I am at Colombo Fort and need to reach Ella under a budget of LKR 2,000, but I have a heavy bag and don't want to walk."*

---

## ✨ Key Features

- **🧠 Autonomous Agentic Loop**: Driven by Alibaba Cloud's Qwen LLM, the agent orchestrates a 5-stage loop: `UNDERSTAND → REASON → ACT → ADAPT → DELIVER`.
- **🛠️ Dynamic Tool Execution**: The agent seamlessly interfaces with backend tools to estimate fares, calculate delay risks, verify seat availability, and inject simulated disruptions.
- **⚡ Constraint-Aware Decision Engine**: Deterministically scores and ranks routes based on hard constraints (budget, time) and soft preferences (less walking, fewer transfers).
- **🎫 Digital Travel Pass**: Automatically issues a scannable QR boarding pass and booking reference once a journey is secured.
- **⚠️ Real-Time Disruption Handling**: Includes a simulation dashboard to inject transit delays and watch the agent dynamically re-evaluate and replan the journey.

---

## 🏗️ Architecture & Tech Stack

RouteWise Agentic is built on a modern, scalable, and cloud-native architecture.

| Component | Technology |
|---|---|
| **AI Orchestration** | Alibaba Cloud Model Studio, **Qwen 3.8 Max** |
| **Backend API** | **Python**, **FastAPI** |
| **Frontend UI** | **React.js**, Vite, TypeScript |
| **Database** | **PostgreSQL**, **PostGIS** (Geospatial) |
| **Machine Learning** | **XGBoost** (fares), **LSTM** (delays) |
| **Cloud & Automation** | **Alibaba Cloud**, Coder Work / Coder Wake |

### System Flow
1. **Frontend**: Accepts natural language input and renders a live timeline of the agent's internal thought process.
2. **Backend**: FastAPI orchestrates the tool calls, normalizes the transit data, and enforces deterministic constraint-checking.
3. **Execution**: Handles booking holds, travel pass generation, and real-time disruption monitoring.

---

## 🚀 Getting Started (Local Development)

### Prerequisites
- **Node.js 18+** (Verified on Node 25)
- **Python 3.10+** (Verified on Python 3.13)

### 1. Start the FastAPI Backend
```bash
cd backend
python -m venv .venv
# Activate the virtual environment:
# Windows: .venv\Scripts\activate
# Mac/Linux: source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload
```
*The backend will be available at `http://localhost:8000` (Swagger UI at `/docs`).*

### 2. Start the React Frontend
Open a new terminal window:
```bash
cd frontend
npm install
npm run dev
```
*The frontend application will be available at `http://localhost:5173`.*

---

## 👥 The Team

RouteWise was built collaboratively, with each member owning a distinct vertical of the platform end-to-end:

- **Sarma HK**  
  *Workstream A: AI Agent & Decision Engine*  
  (LLM Orchestration, Tool Calling, Constraint Extraction, Route Scoring Engine)

- **paulvarshan**  
  *Workstream B: Transit Intelligence & ML*  
  (PostgreSQL/PostGIS, GTFS Integration, XGBoost Fare Prediction, LSTM Delay Models)

- **bajithan**  
  *Workstream C: Autonomous Execution & Cloud*  
  (Booking System, Disruption Injection, Travel Pass Delivery, Cloud Deployment)

---
<div align="center">
  <i>Built with ❤️ for the future of tourism in Sri Lanka.</i>
</div>
