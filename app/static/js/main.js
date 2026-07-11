const visitDate = document.querySelector('input[name="visit_date"]');

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
