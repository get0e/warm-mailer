const BASE_URL = "https://warm-mailer-epom.onrender.com"; 

let emailList = [];
let sentCount = 0;
let failedCount = 0;
let repliesCount = 0;
let uploadedCSV = null;
let loggedInEmail = null;

const fileInput = document.getElementById("csvInput");
const sendBtn = document.getElementById("sendBtn");
const viewRepliesBtn = document.getElementById("viewRepliesBtn");
const textarea = document.getElementById("templateText");
const subjectLine = document.getElementById("subjectLine");
const totalCountDisplay = document.getElementById("total-count");
const statusDiv = document.getElementById("status");

function showStatus(message, isError = false) {
  console.log(` Status: ${message}`);
  if (statusDiv) {
    statusDiv.innerHTML = `<div class="p-3 rounded ${isError ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'}">${message}</div>`;
    setTimeout(() => {
      statusDiv.innerHTML = '';
    }, 10000);
  }
}


window.addEventListener("DOMContentLoaded", async () => {
  console.log("🔍 DOM loaded, checking authentication...");

  const params = new URLSearchParams(window.location.search);
  const email = params.get("email");
  loggedInEmail = email;

  if (!email) {
    console.log(" Missing email in URL, redirecting to auth");
    window.location.href = `${BASE_URL}/authorize`;
    return;
  }

  try {
    showStatus("Checking authentication...");

    console.log(" Sending /check-auth request with email:", email);
    const res = await fetch(`${BASE_URL}/check-auth?email=${email}`);
    const data = await res.json();

    if (!res.ok || !data.authenticated) {
      showStatus(`Not authenticated: ${data.error}`, true);
      statusDiv.innerHTML += `
        <div class="mt-2">
          <button onclick="window.location.href='${BASE_URL}/authorize'" 
                  class="bg-blue-600 hover:bg-blue-700 text-white font-semibold px-4 py-2 rounded">
            Click to Login
          </button>
        </div>
      `;
      return;
    }

    console.log(" Authenticated");
    showStatus(` Logged in as: ${email}`);
    enableForm();

  } catch (err) {
    console.error(" Auth check failed:", err);
    showStatus(` Auth check failed: ${err.message}`, true);
  }
});

function enableForm() {
  if (fileInput) fileInput.disabled = false;
  if (sendBtn) sendBtn.disabled = false;
  if (textarea) textarea.disabled = false;
  if (subjectLine) subjectLine.disabled = false;
}

function disableForm() {
  if (fileInput) fileInput.disabled = true;
  if (sendBtn) sendBtn.disabled = true;
  if (textarea) textarea.disabled = true;
  if (subjectLine) subjectLine.disabled = true;
}

disableForm();

// CSV Upload
fileInput.addEventListener("change", (e) => {
  const file = e.target.files[0];
  if (!file) {
    emailList = [];
    totalCountDisplay.innerText = "0";
    return;
  }

  if (!file.name.endsWith('.csv')) {
    alert("Please upload a CSV file");
    return;
  }

  uploadedCSV = file;

  const reader = new FileReader();
  reader.onload = function (e) {
    try {
      const text = e.target.result;
      emailList = text
        .split(/\r?\n/)
        .map((line) => line.trim())
        .filter((line) => line !== "" && line.includes("@"));

      totalCountDisplay.innerText = emailList.length;

      if (emailList.length === 0) {
        alert("No valid email addresses found.");
      } else {
        showStatus(`Found ${emailList.length} email addresses`);
      }
    } catch (err) {
      console.error("Error reading CSV:", err);
      alert("Error reading CSV file: " + err.message);
    }
  };

  reader.readAsText(file);
});

// Send Emails
sendBtn.addEventListener("click", async (e) => {
  e.preventDefault();

  const template = textarea.value.trim();
  const subject = subjectLine.value.trim();

  if (!uploadedCSV || emailList.length === 0) {
    alert("Please upload a valid CSV file with email addresses.");
    return;
  }

  if (!template || !subject) {
    alert("Please enter both subject and email template.");
    return;
  }

  sendBtn.disabled = true;
  sendBtn.textContent = "Sending...";

  try {
    const formData = new FormData();
    formData.append("csv_file", uploadedCSV);
    formData.append("sender", loggedInEmail); 
    formData.append("subject", subject);
    formData.append("body", template);

    const response = await fetch(`${BASE_URL}/send-emails`, {
      method: "POST",
      body: formData,
    });

    const result = await response.json();

    if (response.ok) {
      sentCount = result.sent || 0;
      failedCount = result.failed || 0;

      document.getElementById("sent-count").innerText = sentCount;
      document.getElementById("failed-count").innerText = failedCount;

      showStatus(` Emails processed. Sent: ${sentCount}, Failed: ${failedCount}`);
    } else {
      throw new Error(result.error || "Unknown server error");
    }

  } catch (err) {
    console.error(" Sending error:", err);
    showStatus(` Error: ${err.message}`, true);
    alert("Could not send emails: " + err.message);
  } finally {
    sendBtn.disabled = false;
    sendBtn.textContent = "Send";
  }
});

// View Replies (Mock)
/*
viewRepliesBtn.addEventListener("click", () => {
  if (repliesCount > 0) {
    alert(`You received ${repliesCount} replies.`);
  } else {
    alert("No replies yet.");
  }
});
*/
