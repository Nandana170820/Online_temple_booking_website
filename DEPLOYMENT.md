# Deployment Notes

## Public hosting

This Flask app is ready for a Python web host such as Render, Railway, PythonAnywhere, or a VPS.

The deployed website should be public. Visitors do not need any secret key to open the site. The `SECRET_KEY`
environment variable is only an internal Flask security setting for sessions; it is not a visitor password and
should never be shown on the website.

For Render:

1. Push this project to GitHub.
2. In Render, create a new Blueprint or Web Service from the repository.
3. Use `render.yaml` if creating a Blueprint.
4. Add these environment variables:
   - `SECRET_KEY` (server-only session secret, not a public access key)
   - `DATABASE_URL`
   - `RAZORPAY_KEY_ID`
   - `RAZORPAY_KEY_SECRET`
5. Deploy the service and use the generated public URL.

Public access checklist:

- Keep the Render service access setting public.
- Do not enable password protection or private preview mode.
- Use test Razorpay keys for recruiter/demo review.
- Switch to live Razorpay keys only after the payment account is approved.

## Razorpay

The payment page supports Razorpay Standard Checkout when these variables are configured:

```text
RAZORPAY_KEY_ID=rzp_test_or_live_key
RAZORPAY_KEY_SECRET=your_key_secret
```

The server creates a Razorpay order, the browser opens Razorpay Checkout, and the server verifies the returned payment signature before marking the booking as paid.

Use test keys while testing. Use live keys only after the Razorpay account is approved for live payments.

## Receipts

Receipt pages are available at:

```text
/receipt/<booking_code>
```

PDF view:

```text
/receipt/<booking_code>.pdf
```

PDF download:

```text
/receipt/<booking_code>.pdf?download=1
```
