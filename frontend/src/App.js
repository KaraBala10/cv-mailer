import React, { useState, useEffect } from "react";
import axios from "axios";
import "./App.css";
import Notification from "./Notification";

const API_BASE_URL =
  process.env.REACT_APP_API_URL || "https://karabala10.pythonanywhere.com/api";

function App() {
  const [recipients, setRecipients] = useState([{ email: "", company: "" }]);
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [senderEmail, setSenderEmail] = useState("");
  const [appPassword, setAppPassword] = useState("");
  const [jobTitle, setJobTitle] = useState("Software Engineer and Developer");
  const [subject, setSubject] = useState("");
  const [pdfFile, setPdfFile] = useState(null);
  const [pdfFileName, setPdfFileName] = useState("");
  const [name, setName] = useState("");
  const [phoneNumber, setPhoneNumber] = useState("");
  const [notification, setNotification] = useState({
    show: false,
    message: "",
    type: "info",
  });
  const [recipientStatus, setRecipientStatus] = useState({});

  useEffect(() => {
    fetchConfig();
  }, []);

  useEffect(() => {
    if (config) {
      setSenderEmail(config.sender_email || "");
      setJobTitle(config.job_title || "Software Engineer and Developer");
      setSubject(config.subject || "");
    }
  }, [config]);

  const fetchConfig = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/config`);
      setConfig(response.data);
    } catch (error) {
      console.error("Failed to fetch config:", error);
    }
  };

  const addRecipient = () => {
    setRecipients([...recipients, { email: "", company: "" }]);
  };

  const removeRecipient = (index) => {
    setRecipients(recipients.filter((_, i) => i !== index));
  };

  const updateRecipient = (index, field, value) => {
    const updated = [...recipients];
    updated[index][field] = value;
    setRecipients(updated);
  };

  const showNotification = (message, type = "info") => {
    setNotification({ show: true, message, type });
    setTimeout(() => {
      setNotification({ show: false, message: "", type: "info" });
    }, 5000);
  };

  const sendEmails = async () => {
    const validRecipients = recipients.filter((r) => r.email.trim() !== "");

    if (validRecipients.length === 0) {
      showNotification(
        "Please add at least one recipient email address",
        "warning"
      );
      return;
    }

    if (!senderEmail.trim()) {
      showNotification("Please enter your sender email address", "warning");
      return;
    }

    if (!appPassword.trim()) {
      showNotification("Please enter your app password", "warning");
      return;
    }

    if (!jobTitle.trim()) {
      showNotification("Please enter your job title", "warning");
      return;
    }

    if (!subject.trim()) {
      showNotification("Please enter email subject", "warning");
      return;
    }

    if (!pdfFile) {
      showNotification("Please select a PDF file to attach", "warning");
      return;
    }

    if (!name.trim()) {
      showNotification("Please enter your name", "warning");
      return;
    }

    if (!phoneNumber.trim()) {
      showNotification("Please enter your phone number", "warning");
      return;
    }

    setLoading(true);
    setResults(null);

    // Initialize status for all recipients
    const initialStatus = {};
    validRecipients.forEach((r) => {
      initialStatus[r.email] = { status: "pending", message: "Waiting..." };
    });
    setRecipientStatus(initialStatus);

    // Convert PDF to base64
    const reader = new FileReader();
    reader.onloadend = async () => {
      const base64Pdf = reader.result.split(",")[1]; // Remove data:application/pdf;base64, prefix

      try {
        // Send emails one by one for live updates
        const results = [];
        let successful = 0;
        let failed = 0;

        for (const recipient of validRecipients) {
          const email = recipient.email.trim();

          // Update status to sending
          setRecipientStatus((prev) => ({
            ...prev,
            [email]: { status: "sending", message: "Sending..." },
          }));

          try {
            const response = await axios.post(`${API_BASE_URL}/send-single`, {
              recipient: recipient,
              sender_email: senderEmail.trim(),
              app_password: appPassword.trim(),
              job_title: jobTitle.trim(),
              subject: subject.trim(),
              pdf_file: base64Pdf,
              pdf_filename: pdfFileName || pdfFile.name,
              name: name.trim(),
              phone_number: phoneNumber.trim().replace(/\D/g, ""), // Remove non-digits
            });

            if (response.data.success) {
              successful++;
              results.push({
                email,
                status: "success",
                message: "Email sent successfully",
              });
              setRecipientStatus((prev) => ({
                ...prev,
                [email]: { status: "success", message: "✅ Sent" },
              }));
            } else {
              failed++;
              results.push({
                email,
                status: "error",
                message: response.data.message || "Failed to send",
              });
              setRecipientStatus((prev) => ({
                ...prev,
                [email]: { status: "error", message: "❌ Failed" },
              }));
            }
          } catch (error) {
            failed++;
            const errorMsg = error.response?.data?.error || error.message;
            results.push({
              email,
              status: "error",
              message: errorMsg,
            });
            setRecipientStatus((prev) => ({
              ...prev,
              [email]: { status: "error", message: `❌ ${errorMsg}` },
            }));
          }

          // Small delay between emails
          await new Promise((resolve) => setTimeout(resolve, 500));
        }

        setResults({
          success: true,
          results,
          summary: {
            successful,
            failed,
            total: validRecipients.length,
          },
        });

        showNotification(
          `Emails sent! Success: ${successful}, Failed: ${failed}`,
          successful === validRecipients.length
            ? "success"
            : failed > 0
            ? "warning"
            : "success"
        );
      } catch (error) {
        console.error("Failed to send emails:", error);
        showNotification(
          `Error: ${error.response?.data?.error || error.message}`,
          "error"
        );
      } finally {
        setLoading(false);
      }
    };

    reader.onerror = () => {
      showNotification("Failed to read PDF file", "error");
      setLoading(false);
    };

    reader.readAsDataURL(pdfFile);
  };

  return (
    <div className="App">
      <div className="container">
        <header className="header">
          <h1>CV-Mailer</h1>
          <p>Job Application Email Automation</p>
        </header>

        <div className="card">
          <h2>Email Configuration</h2>
          <div className="config-form">
            <div className="form-group">
              <label htmlFor="sender-email">Sender Email *</label>
              <input
                id="sender-email"
                type="email"
                placeholder="your-email@gmail.com"
                value={senderEmail}
                onChange={(e) => setSenderEmail(e.target.value)}
                className="input"
                required
              />
            </div>
            <div className="form-group">
              <label htmlFor="app-password">App Password *</label>
              <input
                id="app-password"
                type="password"
                placeholder="Enter your Gmail App Password"
                value={appPassword}
                onChange={(e) => setAppPassword(e.target.value)}
                className="input"
                required
              />
              <small className="help-text">
                <strong>Note:</strong> This is NOT your Gmail password. You need
                to create an App Password from Google Account settings.{" "}
                <a
                  href="https://www.youtube.com/watch?v=weA4yBSUMXs"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="help-link"
                >
                  Watch tutorial video
                </a>
              </small>
            </div>
            <div className="form-group">
              <label htmlFor="job-title">Job Title *</label>
              <input
                id="job-title"
                type="text"
                placeholder="e.g., Software Engineer and Developer"
                value={jobTitle}
                onChange={(e) => setJobTitle(e.target.value)}
                className="input"
                required
              />
              <small className="help-text">
                This will appear in your email template
              </small>
            </div>
            <div className="form-group">
              <label htmlFor="subject">Email Subject *</label>
              <input
                id="subject"
                type="text"
                placeholder="e.g., Job Application – Your Name"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                className="input"
                required
              />
            </div>
            <div className="form-group">
              <label htmlFor="pdf-file">CV/Resume PDF *</label>
              <input
                id="pdf-file"
                type="file"
                accept=".pdf"
                onChange={(e) => {
                  const file = e.target.files[0];
                  if (file) {
                    if (file.type !== "application/pdf") {
                      alert("Please select a PDF file");
                      e.target.value = "";
                      return;
                    }
                    setPdfFile(file);
                    setPdfFileName(file.name);
                  }
                }}
                className="input-file"
                required
              />
              {pdfFileName && (
                <small className="help-text success-text">
                  ✓ Selected: {pdfFileName}
                </small>
              )}
              <small className="help-text">
                Select your CV/Resume PDF file to attach
              </small>
            </div>
            <div className="form-group">
              <label htmlFor="name">Your Name *</label>
              <input
                id="name"
                type="text"
                placeholder="e.g., Mohammad KaraBala"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="input"
                required
              />
              <small className="help-text">
                This will appear in your email template
              </small>
            </div>
            <div className="form-group">
              <label htmlFor="phone-number">Phone Number *</label>
              <input
                id="phone-number"
                type="tel"
                placeholder="e.g., 963949257963 (digits only)"
                value={phoneNumber}
                onChange={(e) => setPhoneNumber(e.target.value)}
                className="input"
                required
              />
              <small className="help-text">
                Enter your phone number (digits only, no spaces or dashes) for
                WhatsApp link
              </small>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <h2>Recipients</h2>
            <button onClick={addRecipient} className="btn btn-add">
              + Add Recipient
            </button>
          </div>

          <div className="recipients-list">
            {recipients.map((recipient, index) => {
              const email = recipient.email.trim();
              const status = recipientStatus[email];
              return (
                <div key={index} className="recipient-item">
                  <div
                    style={{
                      display: "flex",
                      gap: "10px",
                      alignItems: "center",
                      flexWrap: "wrap",
                      width: "100%",
                    }}
                  >
                    <div className="recipient-input-wrapper">
                      <input
                        type="email"
                        placeholder="Email address"
                        value={recipient.email}
                        onChange={(e) =>
                          updateRecipient(index, "email", e.target.value)
                        }
                        className="input"
                        required
                        disabled={loading}
                      />
                      {status && (
                        <span
                          className={`status-indicator status-${status.status}`}
                        >
                          {status.status === "success" && "✅"}
                          {status.status === "error" && "❌"}
                          {status.status === "sending" && "⏳"}
                          {status.status === "pending" && "⏸️"}
                        </span>
                      )}
                    </div>
                    <input
                      type="text"
                      placeholder="Company name (optional)"
                      value={recipient.company}
                      onChange={(e) =>
                        updateRecipient(index, "company", e.target.value)
                      }
                      className="input"
                      disabled={loading}
                      style={{ flex: "1", minWidth: "200px" }}
                    />
                    {recipients.length > 1 && (
                      <button
                        onClick={() => removeRecipient(index)}
                        className="btn btn-remove"
                        disabled={loading}
                      >
                        Remove
                      </button>
                    )}
                  </div>
                  {status && (
                    <div className={`status-message status-${status.status}`}>
                      {status.message}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          <button
            onClick={sendEmails}
            disabled={
              loading || recipients.filter((r) => r.email.trim()).length === 0
            }
            className="btn btn-send"
          >
            {loading ? "Sending Emails..." : "Send All Emails"}
          </button>
        </div>

        {results && (
          <div className="card results-card">
            <h2>Results</h2>
            <div className="results-summary">
              <div className="summary-item success">
                <span className="summary-label">Successful:</span>
                <span className="summary-value">
                  {results.summary.successful}
                </span>
              </div>
              <div className="summary-item failed">
                <span className="summary-label">Failed:</span>
                <span className="summary-value">{results.summary.failed}</span>
              </div>
              <div className="summary-item total">
                <span className="summary-label">Total:</span>
                <span className="summary-value">{results.summary.total}</span>
              </div>
            </div>
            <div className="results-list">
              {results.results.map((result, index) => (
                <div key={index} className={`result-item ${result.status}`}>
                  <span className="result-email">{result.email}</span>
                  <span className={`result-status ${result.status}`}>
                    {result.status === "success" ? "✅" : "❌"} {result.message}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        <footer className="footer">
          <p>
            This site made by{" "}
            <a
              href="https://github.com/KaraBala10"
              target="_blank"
              rel="noopener noreferrer"
              className="footer-link"
            >
              Mohammad KaraBala
            </a>
          </p>
        </footer>
      </div>
      <Notification
        show={notification.show}
        message={notification.message}
        type={notification.type}
        onClose={() =>
          setNotification({ show: false, message: "", type: "info" })
        }
      />
    </div>
  );
}

export default App;
