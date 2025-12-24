# 🚗 Park With Ease – Smart Vehicle Parking Management System

A full-stack parking management system built using **Flask, JWT Auth, SQLite, Vue.js, Bootstrap, and Celery**.  
Users can quickly reserve parking spots, and admins manage lots with real-time analytics.

---

## ✨ Features

### 👤 User Features
- 🔐 Secure login using JWT tokens
- 🅿️ Book parking spots in one click
- 💸 Auto cost calculation when releasing spot
- 📄 Download reservation history as CSV
- 📊 User dashboard with summary stats

### 🛠 Admin Features
- ➕ Create / ✏️ Edit / ❌ Delete Parking Lots
- 🚦 Real-time spot status (Available / Occupied)
- 📈 Summary dashboard with analytics chart
- 👥 View registered users
- 🔍 View reservation details for occupied spots
- ❌ Block lot deletion if any spots are occupied

---

## 🏗 Tech Stack

| Category | Technologies |
|---------|--------------|
| Backend | Flask, SQLAlchemy, JWT |
| Frontend | Vue.js (CDN), Axios, Bootstrap 5 |
| Database | SQLite (default) |
| Tasks | Celery (CSV Export) |

---

## 📂 Project Structure

