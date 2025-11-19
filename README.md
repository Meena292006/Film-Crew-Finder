# 🎬 Film Crew Finder

**Film Crew Finder** is a commission-free web platform that helps **independent filmmakers** connect with **local freelance crew members** — without agencies or middlemen.  
Users can search for film crew by **role**, **name**, or **location**, view profiles, form teams, and collaborate through an integrated chat system.

---

## 🌟 Overview

The film industry relies heavily on networking — yet for independent creators, finding reliable crew members can be difficult and time-consuming.  
**Film Crew Finder** simplifies this process by creating a centralized, transparent platform where filmmakers and crew can discover, connect, and collaborate efficiently.

The system provides an **intuitive search and communication interface**, helping users build their ideal film crew from scratch.

---

## 🧠 Core Features

### 🔍 Smart Search
- Search crew members by **name**, **role**, or **city/location**  
- Location-based matching using the **Haversine formula**  
- Filter results dynamically for faster discovery  

### 💬 Real-Time Chat
- **One-on-one DMs:** Private chat between any two users  
- **Team chat:** Group conversations within project teams  
- Built using Flask-SocketIO for real-time messaging  

### 👥 Team Management
- Send and accept **crew requests** to form or join a team  
- View all accepted members in a shared team dashboard  
- Manage collaboration directly within the platform  

### 🧑‍💼 User Profiles
- Each user has a **profile** with their role, experience, bio, and contact info  
- Option to edit and update portfolio details anytime  

### 🔐 Authentication
- **User registration and login system** using Flask-Login  
- Secure password handling with hashing  
- Role-based access for filmmakers and crew members  

---

## ⚙️ Tech Stack

| Component | Technology |
|------------|-------------|
| **Backend** | Python Flask |
| **Database** | PostgreSQL + SQLAlchemy |
| **Frontend** | Server-rendered HTML (Jinja2) + CSS/JS |
| **Auth** | Flask-Login |
| **Real-Time Chat** | Flask-SocketIO |
| **Location Filter** | Haversine formula (SQL-based distance filtering) |
| **Deploy** | Render (planned) |

---

## 🧩 Local Setup

```bash
# 1️⃣ Clone the repository
git clone https://github.com/yourusername/film-crew-finder.git
cd film-crew-finder

# 2️⃣ Set up virtual environment
python -m venv venv
source venv/bin/activate   # macOS/Linux
venv\Scripts\activate      # Windows

# 3️⃣ Install dependencies
pip install -r requirements.txt

# 4️⃣ Set up environment variables
cp .env.example .env
# Fill in your database URL and secret key

# 5️⃣ Run the app
flask run
