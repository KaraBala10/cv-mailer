import React from "react";
import "./Notification.css";

function Notification({ message, type, onClose, show }) {
  if (!show) return null;

  const typeClass = type || "info";
  const icon =
    type === "success"
      ? "✅"
      : type === "error"
      ? "❌"
      : type === "warning"
      ? "⚠️"
      : "ℹ️";

  return (
    <div
      className={`notification notification-${typeClass} ${show ? "show" : ""}`}
    >
      <div className="notification-content">
        <span className="notification-icon">{icon}</span>
        <span className="notification-message">{message}</span>
        <button className="notification-close" onClick={onClose}>
          ×
        </button>
      </div>
    </div>
  );
}

export default Notification;
