# 📦 Supply Chain Inventory Tracker

A comprehensive multi-location inventory management system for tracking products across the entire supply chain from suppliers to retail stores.

---

## 🎯 Project Overview

This system provides end-to-end visibility and management of inventory across a multi-tier supply chain network. Built with Django (backend) and React (frontend), it handles purchase orders, internal transfers, sales tracking, and automated reorder alerts.

### **Key Features**

✅ **Multi-Location Inventory** - Track stock across suppliers, warehouses, distribution centers, and stores  
✅ **Automated Reorder Alerts** - Smart alerts based on demand patterns and lead times  
✅ **Purchase Order Management** - Complete PO lifecycle with partial receiving  
✅ **Internal Transfers** - Move inventory between locations with approval workflows  
✅ **Sales & Backorders** - Track demand and handle stock-outs automatically  
✅ **Network Visualization** - Interactive supply chain network graph  
✅ **Full Audit Trail** - Complete history of every inventory transaction  
✅ **Role-based Access** - Different permissions for suppliers, managers, analysts  

---

## 🏗️ High-Level System Design

### **Architecture Overview**
```
┌─────────────────────────────────────────────┐
│         FRONTEND (React)                     │
│  Dashboard | Inventory | Orders | Network   │
└─────────────────────────────────────────────┘
                    ↕ REST API
┌─────────────────────────────────────────────┐
│       BACKEND (Django + DRF)                 │
│  Inventory | Orders | Network | Analytics   │
└─────────────────────────────────────────────┘
                    ↕
┌─────────────────────────────────────────────┐
│       DATABASE (PostgreSQL)                  │
│  18+ Interconnected Tables                   │
└─────────────────────────────────────────────┘
                    ↕
┌─────────────────────────────────────────────┐
│       BACKGROUND TASKS (Celery + Redis)      │
│  Reorder Alerts | Email Notifications        │
└─────────────────────────────────────────────┘
```

### **Core Domain Models**

**Network Structure**
- `Location` - Suppliers, warehouses, distribution centers, stores
- `ShippingRoute` - Connections between locations with lead times

**Products & Inventory**
- `Product` - Product catalog
- `ProductSupplier` - Supplier relationships per product
- `InventoryLevel` - Stock quantities per product per location
- `StockMovement` - Audit trail of all inventory changes

**Order Management**
- `PurchaseOrder` → `PurchaseOrderItem` → `PurchaseOrderReceipt`
- `TransferOrder` → `TransferOrderItem`
- `SalesOrder` → `SalesOrderItem` → `BackOrder`

**Intelligence**
- `ReorderAlert` - Automated low-stock notifications
- `DemandHistory` - Historical sales for reorder calculations

### **Key Workflows**

1. **Purchase Order Receipt**
```
   Draft → Confirmed → Shipped → Received → Closed
   └─> Updates inventory automatically (atomic transaction)
```

2. **Internal Transfer**
```
   Requested → Approved → In-Transit → Received
   └─> Deducts from source, adds to destination
```

3. **Reorder Alert**
```
   Celery (hourly) → Calculate reorder points → Check inventory
   └─> Create alerts for low-stock items
```

### **Technical Highlights**

- **Atomic Inventory Updates** - Uses `select_for_update()` to prevent race conditions
- **Multi-echelon Design** - Each location has independent inventory levels
- **Transaction Safety** - All critical operations wrapped in database transactions
- **Background Processing** - Celery for automated tasks
- **RESTful API** - 30+ endpoints with Django REST Framework

---

## 🛠️ Tech Stack

**Backend**
- Django 4.2 + Django REST Framework
- PostgreSQL (database)
- Celery + Redis (background tasks)
- JWT authentication

**Frontend**
- React 18
- Ant Design (UI components)
- React Flow (network visualization)
- Recharts (analytics charts)
- Axios (API calls)

**DevOps**
- Git (version control)
- Gunicorn (production server)
- WhiteNoise (static files)

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- PostgreSQL 14+
- Redis 7.0+
- Node.js 18+ (for frontend)

### Backend Setup
```bash
# Clone and setup
git clone <your-repo>
cd supply-chain-tracker
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Database
createdb supply_chain_db
cp .env.example .env
# Edit .env with your credentials

# Migrate and create superuser
cd backend
python manage.py migrate
python manage.py createsuperuser

# Run server
python manage.py runserver
```

### Start Background Tasks
```bash
# Terminal 2: Redis
redis-server

# Terminal 3: Celery Worker
celery -A supply_chain worker -l info

# Terminal 4: Celery Beat
celery -A supply_chain beat -l info
```

Visit: http://127.0.0.1:8000/admin/

---

## 📁 Project Structure
```
supply-chain-tracker/
├── backend/
│   ├── supply_chain/          # Django project settings
│   ├── inventory/             # Inventory management
│   ├── orders/                # Order management
│   ├── network/               # Supply chain network
│   ├── analytics/             # Reports and analytics
│   └── manage.py
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   └── services/
│   └── package.json
├── docs/
│   ├── DETAILED_DESIGN.md     # Detailed system design
│   └── API_DOCS.md            # API documentation
├── requirements.txt
├── .env.example
├── PROJECT_TRACKER.md         # Task breakdown
└── README.md
```

---

## 🎯 Key Learning Outcomes

**Backend Skills**
- Complex database relationships (18+ interconnected tables)
- Atomic transactions and concurrency handling
- RESTful API design with Django REST Framework
- Background task processing with Celery
- Business logic implementation

**Frontend Skills**
- React component architecture
- API integration with Axios
- State management
- Data visualization
- Responsive UI design

**DevOps Skills**
- Environment configuration
- Database migrations
- Version control with Git
- Deployment strategies

---

## 📊 CV-Worthy Highlights

- "Designed multi-echelon supply chain system with location-specific inventory tracking across 18+ interconnected database tables"
- "Implemented atomic inventory updates using PostgreSQL row-level locking to prevent race conditions"
- "Built automated reorder intelligence system using Celery Beat for hourly stock analysis"
- "Created full audit trail system for regulatory compliance and debugging"
- "Developed RESTful API with 30+ endpoints using Django REST Framework"

---

## 📝 Documentation

- [Detailed System Design](docs/DETAILED_DESIGN.md) - Complete architecture and database schema
- [Project Tracker](PROJECT_TRACKER.md) - 4-week implementation plan
- [API Documentation](docs/API_DOCS.md) - API endpoints and usage

---

## 👤 Author

**[Your Name]**  
Full Stack Development using Python (Django) - University Course Project

GitHub: [your-github]  
Email: [your-email]