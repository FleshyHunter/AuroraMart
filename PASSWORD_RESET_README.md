# Password Reset Feature - SendGrid Integration

## Overview
The forgot password feature is implemented using Django's built-in password reset views with SendGrid email delivery.

## How It Works

1. **User Requests Password Reset**
   - User clicks "Forgot password?" on the login page
   - User enters their email address
   - System sends reset email if the email exists in the database
   - Generic success message shown (security best practice)

2. **Email Delivery**
   - Email sent via SendGrid SMTP
   - Contains a secure, time-limited reset link (24 hours)
   - Both plain text and HTML email formats included

3. **Password Reset**
   - User clicks the link in the email
   - User enters new password (must pass Django validators)
   - Password must be:
     - At least 8 characters
     - Not too similar to username/email
     - Not a common password
     - Not entirely numeric
   - New password is hashed and saved

## Configuration

### SendGrid Settings (in settings.py)
```python
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.sendgrid.net'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'apikey'
EMAIL_HOST_PASSWORD = 'YOUR_SENDGRID_API_KEY'
DEFAULT_FROM_EMAIL = 'noreply@auroramart.com'
```

### URLs
- Password Reset Request: `/password/reset/`
- Password Reset Confirm: `/password/reset/confirm/<uidb64>/<token>/`

## Testing

### Test the password reset flow:

1. Navigate to login page and click "Forgot password?"
2. Enter a registered email address
3. Check your inbox for the reset email
4. Click the reset link
5. Enter and confirm your new password
6. Log in with the new password

### Development Testing
For development, you can view emails in the console by changing the email backend:
```python
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
```

## Security Features

- **Rate Limiting**: Uses Django's built-in token generation (one-time use)
- **Time Expiry**: Reset links expire after 24 hours
- **Generic Messages**: Same message shown whether email exists or not
- **Secure Tokens**: Uses cryptographic tokens (not guessable)
- **Password Validation**: Enforces strong password requirements

## Email Templates

- **Text**: `ecommercemodule/templates/ecommercemodule/email/password_reset_email.txt`
- **HTML**: `ecommercemodule/templates/ecommercemodule/email/password_reset_email.html`
- **Subject**: `ecommercemodule/templates/ecommercemodule/email/password_reset_subject.txt`

## Installation

Install SendGrid Python library:
```bash
pip install sendgrid==6.11.0
```

Or install from requirements.txt:
```bash
pip install -r requirements.txt
```

## Troubleshooting

### Email not sending
1. Check SendGrid API key is correct
2. Verify sender email is verified in SendGrid
3. Check SendGrid dashboard for delivery status
4. Review email logs in Django console

### Link not working
1. Ensure DEBUG=True for local development
2. Check ALLOWED_HOSTS includes your domain
3. Verify URL configuration is correct
4. Link expires after 24 hours

### Password validation errors
- Password too short (min 8 characters)
- Password too similar to username
- Password is too common
- Password is entirely numeric
