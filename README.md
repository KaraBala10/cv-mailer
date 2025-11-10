# 📧 Job Email Automation

A professional email automation tool for job seekers to send personalized job application emails with CV attachments. Built with React frontend and Flask backend, featuring real-time status tracking, customizable email templates, and bulk email sending capabilities.

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
- 🔐 **Secure** - All credentials entered through the UI, no hardcoded passwords
- ⚡ **Live Logs** - See email sending progress in real-time with visual indicators
- 🎯 **Easy to Use** - Simple, intuitive interface for managing recipients and sending emails
- 📱 **Responsive Design** - Works seamlessly on desktop and mobile devices

## 🛠️ Tech Stack

- **Frontend**: React 18, Axios, CSS3
- **Backend**: Flask, Python 3.10+
- **Email**: SMTP (Gmail)
- **Styling**: Custom CSS with modern design principles

## 📋 Prerequisites

Before you begin, ensure you have the following installed:

- **Python 3.10+** - [Download Python](https://www.python.org/downloads/)
- **Node.js 16+** and **npm** - [Download Node.js](https://nodejs.org/)
- **Gmail Account** with App Password enabled
  - [How to create Gmail App Password](https://www.youtube.com/watch?v=weA4yBSUMXs)

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/KaraBala10/job-email-automation.git
cd job-email-automation
```

### 2. Backend Setup

1. Install Python dependencies:

```bash
pip install -r requirements.txt
```

2. Run the Flask backend:

```bash
python app.py
```

The backend will start on `http://localhost:5000`

> **Note**: For production, the backend is deployed at `https://karabala10.pythonanywhere.com`

### 3. Frontend Setup

1. Navigate to the frontend directory:

```bash
cd frontend
```

2. Install dependencies:

```bash
npm install
```

3. Start the React development server:

```bash
npm start
```

The frontend will open at `http://localhost:3000`

> **Note**: The frontend is configured to use the production API at `https://karabala10.pythonanywhere.com` by default. For local development, you can set `REACT_APP_API_URL=http://localhost:5000/api` in a `.env` file in the frontend directory.

## 📖 Usage Guide

### Step 1: Configure Email Settings

1. **Sender Email**: Enter your Gmail address
2. **App Password**: Enter your Gmail App Password (not your regular password)
   - Need help? [Watch tutorial video](https://www.youtube.com/watch?v=weA4yBSUMXs)
3. **Job Title**: Enter your professional title (e.g., "Software Engineer and Developer")
4. **Email Subject**: Customize the subject line for your emails
5. **Your Name**: Enter your full name (appears in email template)
6. **Phone Number**: Enter your phone number (digits only, for WhatsApp link)
7. **CV/Resume PDF**: Select your CV file to attach

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

## 🏗️ Project Structure

```
job-email-automation/
├── app.py                  # Flask backend API
├── code_sender.py          # Email sending logic and utilities
├── email_template.html     # HTML email template
├── requirements.txt        # Python dependencies
├── README.md              # This file
├── frontend/              # React frontend application
│   ├── public/
│   │   └── index.html
│   ├── src/
│   │   ├── App.js         # Main React component
│   │   ├── App.css        # Main styles
│   │   ├── Notification.js # Notification component
│   │   ├── Notification.css # Notification styles
│   │   ├── index.js       # React entry point
│   │   └── index.css      # Global styles
│   └── package.json       # Node.js dependencies
└── .gitignore            # Git ignore rules
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
Get static configuration (SMTP settings).

**Response:**
```json
{
  "template_path": "email_template.html",
  "smtp_server": "smtp.gmail.com",
  "smtp_port": 587,
  "send_delay": 1.0,
  "job_title": "Software Engineer and Developer",
  "subject": ""
}
```

### `POST /api/send-single`
Send a single email to one recipient.

**Request Body:**
```json
{
  "recipient": {
    "email": "recipient@example.com",
    "company": "Company Name"
  },
  "sender_email": "your-email@gmail.com",
  "app_password": "your-app-password",
  "job_title": "Software Engineer",
  "subject": "Job Application",
  "pdf_file": "base64-encoded-pdf",
  "pdf_filename": "CV.pdf",
  "name": "Your Name",
  "phone_number": "1234567890"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Email sent successfully to recipient@example.com"
}
```

### `POST /api/recipients`
Send emails to multiple recipients (legacy endpoint, now uses send-single internally).

## 🎨 Email Template

The email template (`email_template.html`) supports the following placeholders:

- `{greeting}` - Personalized greeting (e.g., "Company Name Hiring Team")
- `{name}` - Your name
- `{job_title}` - Your job title
- `{email}` - Your email address
- `{phone_number}` - Your phone number (for WhatsApp link)

## 🔒 Security Notes

- **Never commit sensitive data** - All credentials are entered through the UI
- **App Password vs Regular Password** - Use Gmail App Password, not your regular Gmail password
- **Keep credentials secure** - Don't share your App Password
- **SMTP Configuration** - Currently configured for Gmail (smtp.gmail.com:587)

## 🐛 Troubleshooting

### Email Sending Fails

1. **Check App Password**: Ensure you're using Gmail App Password, not your regular password
2. **Verify Email**: Make sure your sender email is correct
3. **Check Internet**: Ensure you have a stable internet connection
4. **Gmail Settings**: Verify 2-Step Verification is enabled and App Password is generated

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

⭐ If you find this project helpful, please consider giving it a star on GitHub!
