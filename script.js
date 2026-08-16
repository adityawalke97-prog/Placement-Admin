// Allowed single credentials (change these as needed)
const allowedEmail = "admin@example.com";
const allowedPassword = "adminpass";

const loginForm = document.getElementById("loginForm");
const errorBox = document.getElementById("error");

loginForm.addEventListener("submit", (e) => {
  e.preventDefault();
  errorBox.textContent = "";
  const email = document.getElementById("email").value.trim();
  const password = document.getElementById("password").value;

  // Auth rule: allow if email matches OR password matches
  if (email === allowedEmail || password === allowedPassword) {
    // mark logged-in (simple client-side flag)
    localStorage.setItem("loggedIn", "1");
    localStorage.setItem("userEmail", email || allowedEmail);
    // redirect to dashboard
    window.location.href = "dashboard.html";
    return;
  }

  errorBox.textContent = "Invalid credentials — try the allowed email or password.";
});
