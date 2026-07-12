const visitDate = document.querySelector('input[name="visit_date"]');
const pageMessages = document.body?.dataset || {};
const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const dismissMessage = (button) => {
  button.closest(".flash, .form-message")?.remove();
};

document.querySelectorAll("[data-flash-close]").forEach((button) => {
  button.addEventListener("click", () => dismissMessage(button));
});

const showFormMessage = (form, message, category = "error") => {
  form.querySelector(".form-message")?.remove();
  const wrapper = document.createElement("div");
  wrapper.className = `form-message ${category}`;
  wrapper.setAttribute("role", "alert");

  const text = document.createElement("span");
  text.textContent = message;

  const close = document.createElement("button");
  close.type = "button";
  close.setAttribute("aria-label", "Dismiss message");
  close.textContent = "\u00D7";
  close.addEventListener("click", () => dismissMessage(close));

  wrapper.append(text, close);
  form.prepend(wrapper);
};

document.querySelectorAll("form").forEach((form) => {
  form.setAttribute("novalidate", "novalidate");
  form.addEventListener("submit", (event) => {
    const fields = Array.from(form.querySelectorAll("input, select, textarea"));
    let invalidField = null;
    let message = "";

    for (const field of fields) {
      if (field.disabled || ["hidden", "submit", "button"].includes(field.type)) continue;

      const value = (field.value || "").trim();
      if (field.required && !value) {
        invalidField = field;
        message = pageMessages.requiredMessage || "Please fill all required fields.";
        break;
      }

      if (field.type === "email" && value && !emailPattern.test(value)) {
        invalidField = field;
        message = pageMessages.invalidEmailMessage || "Please enter a valid email address.";
        break;
      }

      const minLength = Number(field.getAttribute("minlength") || 0);
      if (minLength && value.length < minLength) {
        invalidField = field;
        message = pageMessages.minlengthMessage || "Please check the minimum length.";
        break;
      }

      const min = field.getAttribute("min");
      if (min && value && field.type === "number" && Number(value) < Number(min)) {
        invalidField = field;
        message = pageMessages.requiredMessage || "Please fill all required fields.";
        break;
      }

      if (min && value && field.type === "date" && value < min) {
        invalidField = field;
        message = pageMessages.requiredMessage || "Please fill all required fields.";
        break;
      }
    }

    if (!invalidField) return;

    event.preventDefault();
    showFormMessage(form, message);
    invalidField.focus({ preventScroll: true });
    invalidField.scrollIntoView({ block: "center", behavior: "smooth" });
  });
});

if (visitDate) {
  const today = new Date();
  const localDate = new Date(today.getTime() - today.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 10);
  visitDate.min = localDate;
  if (!visitDate.value) visitDate.value = localDate;
}

const bookingForm = document.querySelector("[data-booking-form]");

if (bookingForm) {
  const serviceSelect = bookingForm.querySelector("[data-service-select]");
  const quantityInput = bookingForm.querySelector("[data-quantity-input]");
  const totalAmount = bookingForm.querySelector("[data-total-amount]");

  const getUnitPrice = () => {
    if (serviceSelect) {
      const selectedOption = serviceSelect.options[serviceSelect.selectedIndex];
      return Number(selectedOption?.dataset.price || 0);
    }
    return Number(bookingForm.dataset.unitPrice || 0);
  };

  const updateTotal = () => {
    const quantity = Math.max(Number(quantityInput?.value || 1), 1);
    const total = getUnitPrice() * quantity;
    if (totalAmount) totalAmount.textContent = `\u20B9${total.toFixed(0)}`;
  };

  serviceSelect?.addEventListener("change", updateTotal);
  quantityInput?.addEventListener("input", updateTotal);
  updateTotal();
}

const razorpayForm = document.querySelector("[data-razorpay-form]");

if (razorpayForm) {
  const payButton = razorpayForm.querySelector("[data-razorpay-button]");
  const paymentId = razorpayForm.querySelector("[data-razorpay-payment-id]");
  const orderId = razorpayForm.querySelector("[data-razorpay-order-id]");
  const signature = razorpayForm.querySelector("[data-razorpay-signature]");

  payButton?.addEventListener("click", () => {
    if (!window.Razorpay) {
      payButton.textContent = razorpayForm.dataset.unavailableText || "Payment gateway unavailable";
      payButton.disabled = true;
      return;
    }

    const checkout = new window.Razorpay({
      key: razorpayForm.dataset.key,
      amount: razorpayForm.dataset.amount,
      currency: razorpayForm.dataset.currency || "INR",
      name: razorpayForm.dataset.name,
      description: razorpayForm.dataset.description,
      order_id: razorpayForm.dataset.orderId,
      prefill: {
        name: razorpayForm.dataset.prefillName,
        email: razorpayForm.dataset.prefillEmail,
        contact: razorpayForm.dataset.prefillContact,
      },
      theme: {
        color: "#8f241b",
      },
      handler(response) {
        paymentId.value = response.razorpay_payment_id || "";
        orderId.value = response.razorpay_order_id || "";
        signature.value = response.razorpay_signature || "";
        razorpayForm.submit();
      },
    });

    checkout.open();
  });
}
