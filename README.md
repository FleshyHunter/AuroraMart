# AuroraMart

AuroraMart is a full-stack ecommerce platform built with Django that combines online shopping, inventory management, customer profiling, and machine-learning-powered product recommendations.

The platform provides customer-facing shopping experiences, administrative inventory management, and data-driven recommendation capabilities through a centralized Django application.

>Django ecommerce platform featuring inventory management, customer profiling, ML-powered category prediction, association-rule product recommendations, and administrative product management.
## What It Does

* Displays product catalogues organized by category and subcategory.
* Supports customer registration and profile management.
* Tracks inventory levels and product availability.
* Manages product images and media assets.
* Provides administrative management of products and customers.
* Predicts customer purchasing preferences using a machine learning classifier.
* Generates product recommendations using association rule mining.
* Supports category exploration and frequently-bought-together recommendations.
* Includes utilities for automated product image population.

AuroraMart is designed to explore modern ecommerce workflows while integrating machine learning models directly into the application layer.

## Tech Stack

* Backend: Django 5.2
* Database: SQLite (Development)
* ORM: Django ORM
* Machine Learning: Scikit-learn, Pandas, Joblib
* Frontend: Django Templates
* Administration: Django Admin + Custom Admin Panel
* Media Storage: Django Media Framework

## Project Structure

```text
.
├── auroramart
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   ├── wsgi.py
│   │
│   ├── ml
│   │   ├── classifier.py
│   │   ├── recommender.py
│   │   └── models
│   │
│   ├── management
│   │   └── commands
│   │       └── populate_product_images.py
│   │
│   └── migrations
│
├── ecommercemodule
├── admin_panel
├── media
├── static
└── db.sqlite3
```

## Core Domain Models

### Category

Represents top-level product classifications.

Fields:

* name
* slug

Features:

* Unique category names
* SEO-friendly slugs
* Alphabetical ordering

### SubCategory

Represents subdivisions within a category.

Fields:

* category
* name
* slug

Features:

* Category-specific uniqueness constraints
* Hierarchical categorization

### Product

Represents products available for purchase.

Fields include:

* SKU
* Name
* Description
* Category
* Subcategory
* Quantity on hand
* Reorder quantity
* Unit price
* Rating
* Active status
* Product image fields

Features:

* Inventory tracking
* Category validation
* Product image fallback handling
* Database indexing for performance

### Customer

Represents customer demographic information.

Fields include:

* User account linkage
* Age
* Gender
* Occupation
* Employment status
* Education
* Household size
* Income
* Preferred category

Features:

* Built-in validation
* Optional integration with Django authentication
* Machine learning recommendation support

## Machine Learning Components

### Customer Preference Classifier

File:

```text
auroramart/ml/classifier.py
```

Purpose:

Predicts a customer's preferred product category using a trained classification model.

Features:

* Loads trained Joblib model.
* Supports configurable model paths.
* Performs categorical encoding.
* Aligns features with training schema.
* Returns predicted category recommendations.

Default model:

```text
auroramart/ml/models/b2c_customers_100.joblib
```

### Product Recommendation Engine

File:

```text
auroramart/ml/recommender.py
```

Purpose:

Provides product recommendations using association rule mining.

Features:

* Frequently bought together recommendations.
* Shopping cart add-on recommendations.
* Category exploration recommendations.
* Confidence and lift-based ranking.

Default rules dataset:

```text
auroramart/ml/models/b2c_products_500_transactions_50k.joblib
```

## Administration

The application registers the following models for administration:

* Category
* SubCategory
* Product
* Customer

Administrative functionality includes:

* Product inventory management.
* Product image previews.
* Category management.
* Customer management.
* Search and filtering tools.
* Bulk editing of inventory and pricing information.

## URL Routing

Primary routes:

```text
/
/store/
/admin_panel/
```

Features:

* Root route redirects to the storefront.
* Store functionality is handled by the ecommerce module.
* Administrative functionality is provided through a custom admin panel.
* Media files are served automatically during development.

## Management Commands

### Populate Product Images

Command:

```bash
python manage.py populate_product_images
```

Purpose:

Automatically assigns predefined image URLs to products based on category and subcategory mappings.

Supported options:

```bash
python manage.py populate_product_images --force
python manage.py populate_product_images --limit 10
python manage.py populate_product_images --category Electronics
```

The command uses static URL mappings and does not perform web scraping.

## Database Migrations

### Initial Migration

```text
0001_initial.py
```

Creates:

* Category
* SubCategory
* Product
* Customer

Includes:

* Database indexes
* Validation constraints
* Foreign key relationships

### Product Image Migration

```text
0002_product_image_product_image_url.py
```

Adds:

* image
* image_url

to the Product model.

## Local Development

Install dependencies:

```bash
pip install -r requirements.txt
```

Apply migrations:

```bash
python manage.py migrate
```

Start development server:

```bash
python manage.py runserver
```

Default local services:

```text
Application: http://localhost:8000
Database: SQLite (db.sqlite3)
Media: /media/
Static: /static/
```

## Current Status

Implemented:

* Product catalogue management.
* Category and subcategory hierarchy.
* Customer demographic modelling.
* Inventory management.
* Product image management.
* Machine learning customer classification.
* Association-rule product recommendations.
* Administrative management tools.
* Automated image population command.

Future Improvements:

* Production database support.
* Cloud media storage.
* Real-time recommendation serving.
* Recommendation analytics.
* User behavior tracking.
* Containerized deployment.

## Notes

* The Django secret key is currently stored in source code and should be moved to environment variables for production deployment.
* `DEBUG=True` and an empty `ALLOWED_HOSTS` configuration indicate a development-only setup.
* Machine learning artifacts are stored as Joblib binaries and should be versioned carefully.
* The built-in Django admin route is disabled while a custom administrative interface is exposed through `/admin_panel/`.
* Verify the intentional separation between Product models referenced by the recommendation engine and the shared domain model layer.
