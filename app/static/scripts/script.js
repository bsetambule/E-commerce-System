// عناصر
const menuToggle = document.getElementById("menuToggle");
const sidebar = document.getElementById("sidebar");
const overlay = document.getElementById("overlay");

// ===============================
// SIDEBAR MENU LOGIC
// ===============================
if (menuToggle && sidebar && overlay) {

  const openClasses = () => {
    sidebar.classList.add("show");
    overlay.classList.add("show");
    menuToggle.classList.add("active");
  };

  const closeClasses = () => {
    sidebar.classList.remove("show");
    overlay.classList.remove("show");
    menuToggle.classList.remove("active");
  };

  // Toggle menu
  menuToggle.addEventListener("click", () => {
    sidebar.classList.toggle("show");
    overlay.classList.toggle("show");
    menuToggle.classList.toggle("active");
  });

  // Close when clicking overlay
  overlay.addEventListener("click", closeClasses);

  // Close when clicking any link
  document.querySelectorAll("#sidebar a").forEach(link => {
    link.addEventListener("click", closeClasses);
  });
}


// ===============================
// PHONE INPUT HANDLING (LEGACY FUNCTION)
// ===============================
function initPhoneInput() {
  const phoneInput = document.getElementById("phoneInput");
  const countryCode = document.getElementById("countryCode");
  const fullPhone = document.getElementById("fullPhone");

  if (!phoneInput || !countryCode || !fullPhone) return;

  phoneInput.addEventListener("input", () => {
    phoneInput.value = phoneInput.value.replace(/\D/g, "");
  });

  function buildPhone() {
    const code = countryCode.value;
    const number = phoneInput.value.trim();

    if (!number) {
      fullPhone.value = "";
      return false;
    }

    if (number.length < 7 || number.length > 12) {
      phoneInput.setCustomValidity("Enter a valid phone number");
      return false;
    }

    phoneInput.setCustomValidity("");
    fullPhone.value = `${code}${number}`;
    return true;
  }

  phoneInput.addEventListener("blur", buildPhone);

  // exposed globally (unchanged behavior)
  window.validatePhone = buildPhone;
}


// ===============================
// MAIN INITIALIZATION
// ===============================
document.addEventListener("DOMContentLoaded", () => {

  // keep legacy function active (was previously unused)
  initPhoneInput();

  const phoneInput = document.getElementById("phoneInput");
  const countryCode = document.getElementById("countryCode");
  const fullPhone = document.getElementById("fullPhone");
  const form = document.getElementById("signupForm");

  // ===============================
  // FLASH MESSAGES
  // ===============================
  const flashes = document.querySelectorAll(".flash-message");

  flashes.forEach((flash) => {

    const removeFlash = () => {
      flash.style.animation = "fadeOut 0.4s ease forwards";

      setTimeout(() => {
        flash.remove();
      }, 400);
    };

    setTimeout(removeFlash, 4000);

    flash.querySelector(".flash-close")
      ?.addEventListener("click", removeFlash);
  });

  // Exit if not on signup page
  if (!phoneInput || !countryCode || !fullPhone || !form) return;

  function updateFullPhone() {
    const code = countryCode.value;
    const number = phoneInput.value.replace(/\D/g, "");
    fullPhone.value = code + number;
  }

  phoneInput.addEventListener("input", updateFullPhone);
  countryCode.addEventListener("change", updateFullPhone);

  form.addEventListener("submit", () => {
    updateFullPhone();
  });
});