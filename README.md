# Fast-Food-Website

# Street Bites – Online Food Ordering Website

**Good Food. Good Mood.**

Street Bites is a South African-inspired online fast-food ordering website developed to provide customers with a convenient and user-friendly food ordering experience.

The platform allows customers to explore a variety of meals, create accounts, manage shopping carts and place orders for delivery or collection. It also features an integrated chatbot to assist users and improve their interaction with the website.

The project combines backend development, database management and frontend technologies to create a functional restaurant ordering platform.

## Website Features

### Customer Features
- **User Registration:** Create a personal customer account.
- **User Login & Authentication:** Secure account access.
- **Food Menu:** Browse available meals and prices.
- **Shopping Cart:** Add, update and remove food items.
- **Checkout System:** Place orders for delivery or collection.
- **Order Confirmation:** Receive confirmation after placing an order.
- **Password Recovery:** Reset forgotten passwords through email.
- **Contact Page:** Submit enquiries through the website.
- **Location Page:** Find information about the restaurant.
- **Responsive Design:** Access the website across different screen sizes.

### Chatbot Integration
Street Bites includes a chatbot designed to improve customer interaction and provide assistance while browsing the website.

The chatbot helps make the website more interactive and provides an additional way for customers to get information and assistance.

### Admin Features
- View customer orders.
- Monitor order details.
- Update order statuses.
- Manage the order fulfilment process.

## Technologies & Tools Used

| Technology | Purpose |
|---|---|
| Python | Backend programming |
| Flask | Web application framework |
| HTML5 | Website structure |
| CSS3 | Styling and visual design |
| JavaScript | Interactive website functionality |
| Bootstrap 5 | Responsive website components |
| SQLite | Database storage |
| Jinja2 | Dynamic page rendering |
| Werkzeug | Password hashing and security |
| Gmail SMTP | Password recovery emails |
| Visual Studio Code | Development environment |
| Git & GitHub | Version control and project hosting |

## Food Categories

Street Bites offers a selection of popular fast-food meals inspired by South African food culture.

- Burgers
- Crispy Chicken
- Chicken & Chips
- Chicken Wraps
- Regular and Loaded Chips
- Soft Drinks
- Traditional South African AmaGwinya

## Project Structure

```text
Street-Bites/
│
├── app.py
├── database.py
├── street_bites.db
│
├── Static/
│   ├── Style.css
│   ├── burger.png
│   ├── img.png
│   ├── street.png
│   └── wings.png
│
├── Templates/
│   ├── Base.html
│   ├── Index.html
│   ├── About.html
│   ├── Menu.html
│   ├── signup.html
│   ├── login.html
│   ├── cart.html
│   ├── checkout.html
│   ├── order_confirmation.html
│   ├── admin_orders.html
│   ├── contact_us.html
│   ├── forgot_password.html
│   ├── reset_password.html
│   └── where_to_find_us.html
│
└── README.md
```

## Installation & Setup

Follow these steps to run the project locally.

**1. Clone the repository**

```bash
git clone YOUR_REPOSITORY_URL
```

**2. Navigate to the project folder**

```bash
cd Street-Bites
```

**3. Create a virtual environment**

```bash
python -m venv .venv
```

**4. Activate the environment (Windows)**

```powershell
.venv\Scripts\Activate.ps1
```

**5. Install dependencies**

```bash
pip install Flask Werkzeug
```

**6. Configure environment variables**

The application uses environment variables for its secret key, administrator email and Gmail credentials.

```powershell
$env:STREET_BITES_SECRET_KEY = "your-secret-key"
$env:STREET_BITES_ADMIN_EMAIL = "your-admin-email"
$env:MAIL_USERNAME = "your-gmail-address"
$env:MAIL_APP_PASSWORD = "your-gmail-app-password"
```

Gmail password recovery requires Google 2-Step Verification and an App Password.

**7. Run the application**

```bash
python app.py
```

Open your browser:

```text
http://127.0.0.1:5000/
```

## Database

Street Bites uses SQLite for data storage and management.

The database supports:
- Customer account information.
- Hashed user passwords.
- Password reset tokens.
- Customer orders.
- Order items and quantities.
- Order totals and statuses.

## Security Features

- Password hashing using Werkzeug.
- Secure, randomly generated password reset tokens.
- SHA-256 hashing of stored reset tokens.
- Time-limited password reset links.
- Session-based authentication.
- Restricted administrator access.

## Future Enhancements

Planned improvements include:

- Online payment gateway integration.
- Real-time order tracking.
- Enhanced chatbot capabilities.
- Customer order history.
- Improved admin dashboard and reporting.
- Email notifications for order updates.

## About the Developer

**Banele Seko**

ICT Graduate | Aspiring Software Developer | Data & Technology Enthusiast

I am an ICT graduate from Durban University of Technology with an interest in software development, data analytics, data science and emerging technologies.

I enjoy developing practical applications that solve real-world problems while continuously expanding my technical knowledge.

Street Bites is a personal development project that has allowed me to apply my knowledge of Python, Flask, SQL, frontend development, database integration and application security.

### Connect With Me

- **LinkedIn:** [Banele Seko](https://linkedin.com/in/banele-seko/)
- **GitHub:** [BaneleSeko](https://github.com/BaneleSeko)
- **Kaggle:** [Banele Seko](https://kaggle.com/baneleseko)

---

**Developed by Banele Seko**

*Street Bites – Good Food. Good Mood.*

© 2026 Street Bites. All rights reserved.
