const API_URL = "http://localhost:5000/api/search";
const AUTH_URL = "http://localhost:5000/api/auth/gmail";
const CALLBACK_URL = "http://localhost:5000/api/auth/callback";

let gmailTokens = null;

const form = document.getElementById("searchForm");
const serverSelect = document.getElementById("server");
const gmailSection = document.getElementById("gmailSection");
const passwordSection = document.getElementById("passwordSection");
const googleSignIn = document.getElementById("googleSignIn");
const googleSignOut = document.getElementById("googleSignOut");
const oauthSuccess = document.getElementById("oauthSuccess");
const oauthStatus = document.getElementById("oauthStatus");
const searchBtn = document.getElementById("searchBtn");
const btnText = searchBtn.querySelector(".btn-text");
const btnLoading = searchBtn.querySelector(".btn-loading");
const errorDiv = document.getElementById("error");
const resultsDiv = document.getElementById("results");
const emailList = document.getElementById("emailList");
const resultCount = document.getElementById("resultCount");

async function loadTokens() {
  const data = await chrome.storage.local.get(["gmailTokens"]);
  if (data.gmailTokens) {
    gmailTokens = data.gmailTokens;
    showConnected(true);
  }
}

function showConnected(connected) {
  oauthStatus.classList.toggle("hidden", connected);
  oauthSuccess.classList.toggle("hidden", !connected);
}

serverSelect.addEventListener("change", () => {
  const isGmail = serverSelect.value === "gmail";
  gmailSection.classList.toggle("hidden", !isGmail);
  passwordSection.classList.toggle("hidden", isGmail);
});

googleSignIn.addEventListener("click", async () => {
  try {
    const response = await fetch(AUTH_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ redirect_uri: CALLBACK_URL }),
    });

    const data = await response.json();
    if (data.authorization_url) {
      chrome.identity.launchWebAuthFlow(
        {
          url: data.authorization_url,
          interactive: true,
        },
        async (redirectUrl) => {
          if (chrome.runtime.lastError || !redirectUrl) {
            showError("Google sign-in was cancelled");
            return;
          }

          const url = new URL(redirectUrl);
          const code = url.searchParams.get("code");

          if (!code) {
            showError("No authorization code received");
            return;
          }

          const callbackResponse = await fetch(CALLBACK_URL, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ code, redirect_uri: CALLBACK_URL }),
          });

          const tokenData = await callbackResponse.json();

          if (tokenData.error) {
            showError(tokenData.error);
            return;
          }

          gmailTokens = {
            access_token: tokenData.access_token,
            refresh_token: tokenData.refresh_token,
            client_id: tokenData.client_id,
            client_secret: tokenData.client_secret,
          };

          await chrome.storage.local.set({ gmailTokens });
          showConnected(true);
        }
      );
    }
  } catch (err) {
    showError("Cannot connect to backend. Make sure the Python server is running.");
  }
});

googleSignOut.addEventListener("click", async () => {
  gmailTokens = null;
  await chrome.storage.local.remove("gmailTokens");
  showConnected(false);
});

form.addEventListener("submit", async (e) => {
  e.preventDefault();

  const server = serverSelect.value;
  const recipient = document.getElementById("recipient").value;
  const keywords = document.getElementById("keywords").value;

  if (server === "gmail") {
    if (!gmailTokens) {
      showError("Please sign in with Google first");
      return;
    }
  } else {
    const emailAddr = document.getElementById("email").value;
    const password = document.getElementById("password").value;
    if (!emailAddr || !password) {
      showError("Email and password are required");
      return;
    }
  }

  if (!recipient && !keywords) {
    showError("Please enter a recipient or keywords");
    return;
  }

  showLoading(true);
  hideError();
  hideResults();

  try {
    const body = { server, recipient, keywords };

    if (server === "gmail") {
      Object.assign(body, gmailTokens);
    } else {
      body.email = document.getElementById("email").value;
      body.password = document.getElementById("password").value;
    }

    const response = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    const data = await response.json();

    if (!response.ok) {
      showError(data.error || "Search failed");
      return;
    }

    showResults(data.emails, data.count);
  } catch (err) {
    showError("Cannot connect to backend. Make sure the Python server is running.");
  } finally {
    showLoading(false);
  }
});

function showLoading(loading) {
  btnText.classList.toggle("hidden", loading);
  btnLoading.classList.toggle("hidden", !loading);
  searchBtn.disabled = loading;
}

function showError(message) {
  errorDiv.textContent = message;
  errorDiv.classList.remove("hidden");
}

function hideError() {
  errorDiv.classList.add("hidden");
}

function hideResults() {
  resultsDiv.classList.add("hidden");
}

function showResults(emails, count) {
  resultCount.textContent = count;
  emailList.innerHTML = "";

  if (count === 0) {
    emailList.innerHTML = '<p class="no-results">No emails found</p>';
  } else {
    emails.forEach((email) => {
      const card = document.createElement("div");
      card.className = "email-card";
      card.innerHTML = `
        <div class="email-subject">${escapeHtml(email.subject)}</div>
        <div class="email-meta">
          <span class="email-from">From: ${escapeHtml(email.from)}</span>
          <span class="email-date">${escapeHtml(email.date)}</span>
        </div>
        <div class="email-preview">${escapeHtml(email.body)}</div>
      `;
      emailList.appendChild(card);
    });
  }

  resultsDiv.classList.remove("hidden");
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

loadTokens();
