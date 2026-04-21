# 📧 CV-Mailer

**cv-mailer** — a small full-stack app for job seekers to send personalized application emails with a CV PDF attached. React frontend, Flask API, Gmail over **OAuth2 (XOAUTH2)** only (browser sign-in and/or server refresh token). Real-time per-recipient status, HTML template placeholders, bulk send.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![React](https://img.shields.io/badge/React-18.2.0-61dafb.svg)
![Flask](https://img.shields.io/badge/Flask-3.0.0-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## ✨ Features

- 🚀 **Bulk Email Sending** - Send personalized emails to multiple recipients simultaneously
- 📊 **Real-time Status Tracking** - Live updates showing the status of each email (pending, sending, success, error)
- 🎨 **Modern UI** - Clean, minimalist interface built with React
- 📝 **Customizable Templates** - Personalized email templates with dynamic placeholders
- 📎 **PDF Attachment** - Attach your CV/Resume directly from the interface
- 🔐 **Secure** - Gmail via Google OAuth2 (browser and/or server refresh token), no app passwords
- ⚡ **Live Logs** - See email sending progress in real-time with visual indicators
- 🎯 **Easy to Use** - Simple, intuitive interface for managing recipients and sending emails
- 📱 **Responsive Design** - Works seamlessly on desktop and mobile devices

## 🛠️ Tech Stack

- **Frontend**: React 18, Axios, Google Identity Services (OAuth token client), CSS3
- **Backend**: Flask 3, Flask-CORS, Python 3.10+
- **Auth / email**: `google-auth`, `google-auth-oauthlib`, Gmail SMTP + XOAUTH2 (`gmail_oauth.py`)
- **Config**: `python-dotenv` (optional `.env` beside `app.py`)

## 📋 Prerequisites

Before you begin, ensure you have the following installed:

- **Python 3.10+** - [Download Python](https://www.python.org/downloads/)
- **Node.js 16+** and **npm** - [Download Node.js](https://nodejs.org/)
- **Google Cloud / OAuth** – Web client ID for “Sign in with Google”, and/or server-side Gmail OAuth (`GMAIL_OAUTH_*` env vars) for sending without browser tokens

## 🚀 Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/KaraBala10/cv-mailer.git
cd cv-mailer
```

### 2. Backend setup

1. Create a virtual environment (recommended), then install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

2. **Environment variables** (see **Prerequisites** above): put a `.env` in the repo root next to `app.py`, for example:

   - `GOOGLE_OAUTH_WEB_CLIENT_ID` — Web client ID for the React app (Sign in with Google)
   - `GMAIL_OAUTH_CLIENT_ID`, `GMAIL_OAUTH_CLIENT_SECRET`, `GMAIL_OAUTH_REFRESH_TOKEN` — optional server-side Gmail OAuth for sending without a browser token

3. Run the Flask app:

```bash
python app.py
```

The API listens on `http://localhost:5000` (override with `FLASK_PORT` if needed).

> **Note:** A production deployment example: `https://karabala10.pythonanywhere.com` (paths under `/api/...`).

### 3. Frontend setup

```bash
cd frontend
npm install
npm start
```

Opens at `http://localhost:3000`.

Optional `frontend/.env`:

- `REACT_APP_API_URL=http://localhost:5000/api` — point the UI at a local API
- `REACT_APP_GOOGLE_OAUTH_CLIENT_ID=...` — Web client ID if you do not expose it via `/api/config`

The bundled default API base in `App.js` may target a hosted backend; override with `REACT_APP_API_URL` for local runs.

## 📖 Usage Guide

### Step 1: Configure Email Settings

1. **Google**: Sign in with Google (browser OAuth) when the app shows the button, or rely on server OAuth if your deployment has refresh-token env vars configured
2. **Job Title**: Enter your professional title (e.g., "Software Engineer and Developer")
3. **Email Subject**: Customize the subject line for your emails
4. **Your Name**: Enter your full name (appears in email template)
5. **Phone Number**: Enter your phone number (digits only, for WhatsApp link)
6. **CV/Resume PDF**: Select your CV file to attach

### Step 2: Add Recipients

1. Click **"+ Add Recipient"** to add email addresses
2. Enter recipient email address (required)
3. Enter company name (optional, for personalized greeting)
4. Add as many recipients as needed

### Step 3: Send Emails

1. Click **"Send All Emails"** button
2. Watch real-time status updates:
   - ⏸️ **Pending** - Waiting to send
   - ⏳ **Sending** - Currently being sent
   - ✅ **Success** - Email sent successfully
   - ❌ **Error** - Failed to send (check error message)
3. View summary of successful and failed sends

## 🏗️ Project structure

```
cv-mailer/
├── app.py                 # Flask API (routes, OAuth wiring)
├── gmail_oauth.py         # XOAUTH2 + refresh-token helpers
├── code_sender.py         # SMTP helpers, template load, send_one
├── email_template.html    # HTML email body template
├── requirements.txt
├── README.md
├── .env                   # optional; not committed (secrets)
├── frontend/
│   ├── public/index.html
│   ├── src/
│   │   ├── App.js
│   │   ├── App.css
│   │   ├── Notification.js
│   │   ├── Notification.css
│   │   ├── index.js
│   │   └── index.css
│   └── package.json
└── .gitignore
```

## 🔌 API Endpoints

### `GET /api/health`
Health check endpoint.

**Response:**
```json
{
  "status": "ok",
  "message": "Email sender API is running"
}
```

### `GET /api/config`
SMTP defaults plus OAuth hints for the UI.

**Response (example):**
```json
{
  "template_path": "/absolute/or/repo/path/email_template.html",
  "smtp_server": "smtp.gmail.com",
  "smtp_port": 587,
  "send_delay": 1.0,
  "job_title": "Software Engineer and Developer",
  "subject": "",
  "server_oauth_configured": false,
  "google_oauth_client_id": "your-client-id.apps.googleusercontent.com"
}
```

`google_oauth_client_id` is `GOOGLE_OAUTH_WEB_CLIENT_ID` or falls back to `GMAIL_OAUTH_CLIENT_ID`. `server_oauth_configured` is true when refresh token + client id + secret are set on the server.

### `POST /api/send-single`
Send a single email to one recipient.

**Request Body:**
```json
{
  "recipient": {
    "email": "recipient@example.com",
    "company": "Company Name"
  },
  "sender_email": "",
  "oauth_access_token": "optional-browser-access-token",
  "job_title": "Software Engineer",
  "subject": "Job Application",
  "pdf_file": "base64-encoded-pdf",
  "pdf_filename": "CV.pdf",
  "name": "Your Name",
  "phone_number": "1234567890"
}
```

Omit `oauth_access_token` if the server has `GMAIL_OAUTH_REFRESH_TOKEN` (and client id/secret) set. `sender_email` can be empty when OAuth can resolve the address via userinfo.

**Response:**
```json
{
  "success": true,
  "message": "Email sent successfully to recipient@example.com"
}
```

### `POST /api/recipients`
Bulk send: accepts a `recipients` array and the same auth/fields as single-send (OAuth only).

## 🎨 Email Template

The email template (`email_template.html`) supports the following placeholders:

- `{greeting}` - Personalized greeting (e.g., "Company Name Hiring Team")
- `{name}` - Your name
- `{job_title}` - Your job title
- `{email}` - Your email address
- `{phone_number}` - Your phone number (for WhatsApp link)

## 🔒 Security Notes

- **Never commit sensitive data** – OAuth client secrets and refresh tokens belong in env vars, not the repo
- **Browser tokens** – Short-lived; do not log or persist access tokens outside `sessionStorage` for this app
- **SMTP Configuration** – Gmail (`smtp.gmail.com:587`) with OAuth2 (XOAUTH2)

## 🐛 Troubleshooting

### Email Sending Fails

1. **OAuth**: Confirm Google OAuth client IDs, redirect/JS origins, and consent screen scopes (`mail.google.com`, `userinfo.email`, etc.)
2. **Server OAuth**: If using refresh token on the server, verify `GMAIL_OAUTH_*` env vars match the account you send from
3. **Check Internet**: Ensure you have a stable internet connection

### Backend Not Starting

1. Check Python version: `python --version` (should be 3.10+)
2. Verify dependencies: `pip install -r requirements.txt`
3. Check port 5000 is available

### Frontend Not Starting

1. Check Node.js version: `node --version` (should be 16+)
2. Clear node_modules and reinstall: `rm -rf node_modules && npm install`
3. Check port 3000 is available

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License.

## 👤 Author

**Mohammad KaraBala**

- GitHub: [@KaraBala10](https://github.com/KaraBala10)
- Email: mohammad.karabala@gmail.com

## 🙏 Acknowledgments

- Built with [React](https://reactjs.org/) and [Flask](https://flask.palletsprojects.com/)
- Email template design inspired by modern email best practices
- Icons and UI elements designed for optimal user experience

## 📊 Features Roadmap

- [ ] Email scheduling
- [ ] Email templates library
- [ ] CSV import for recipients
- [ ] Email analytics dashboard
- [ ] Support for other email providers (Outlook, Yahoo, etc.)
- [ ] Email draft saving
- [ ] Recipient groups management

---

⭐ If you find **cv-mailer** useful, consider starring [KaraBala10/cv-mailer](https://github.com/KaraBala10/cv-mailer) on GitHub.
