"""Sample customers and suppliers, for trying the app out.

Run from the backend folder:

    uv run python -m scripts.seed_sample_data

Everything goes through the application's own services, so codes (CUST-0002,
SUP-0002-BR01...), GST and pin code checks, and the stock ledger behave
exactly as they do for records typed into the app. Opening stock is booked as
an "Opening stock" receipt, so Inventory and each product's movement history
explain every unit.

Safe to run again: a customer, supplier, category or product that already
exists (by name, or by SKU for products) is left as it is. The companies are
made up for testing; none is a real customer or supplier.
"""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Category, Customer, Product, Supplier, User
from app.schemas.category import CategoryCreate
from app.schemas.customer import CustomerBranchCreate, CustomerCreate
from app.schemas.product import ProductCreate
from app.schemas.supplier import SupplierBranchCreate, SupplierCreate
from app.services import categories, customers, products, suppliers

TN = "Tamil Nadu"

CUSTOMERS: list[dict[str, Any]] = [
    {
        "name": "Kaveri Chemicals Pvt Ltd",
        "contact_person": "Mr. R. Senthil Kumar",
        "designation": "Purchase Manager",
        "phones": ["9842012345", "0427-2445566"],
        "emails": ["purchase@kaverichem.example"],
        "gstin": "33AABCK1234F1Z5",
        "billing_address_line1": "SIPCOT Industrial Complex, Plot 14",
        "billing_city": "Mettur Dam",
        "billing_state": TN,
        "billing_pincode": "636401",
        "branches": [
            {
                "name": "Cuddalore Plant",
                "gstin": "33AABCK1234F2Z4",
                "contact_person": "Mr. A. Prakash",
                "designation": "Maintenance Engineer",
                "phones": ["9842098765"],
                "address_line1": "SIPCOT Phase II",
                "city": "Cuddalore",
                "state": TN,
                "pincode": "607005",
            },
            {
                "name": "Bengaluru Office",
                "gstin": "29AABCK1234F1Z9",
                "emails": ["blr@kaverichem.example"],
                "address_line1": "No. 45, 2nd Main, Peenya Industrial Area",
                "city": "Bengaluru",
                "state": "Karnataka",
                "pincode": "560058",
            },
        ],
    },
    {
        "name": "Salem Textile Processors",
        "contact_person": "Mr. K. Murugesan",
        "designation": "Proprietor",
        "phones": ["9443056789"],
        "emails": ["stp.salem@example.com"],
        "gstin": "33AAFFS5678K1Z2",
        "billing_address_line1": "12, Omalur Main Road",
        "billing_city": "Salem",
        "billing_state": TN,
        "billing_pincode": "636009",
        "branches": [],
    },
    {
        "name": "Erode Sugars & Distilleries Ltd",
        "contact_person": "Ms. P. Lakshmi",
        "designation": "Stores Officer",
        "phones": ["9789011223"],
        "emails": ["stores@erodesugars.example", "accounts@erodesugars.example"],
        "gstin": "33AACCE4321M1Z8",
        "billing_address_line1": "Sathy Road, Kavindapadi",
        "billing_city": "Erode",
        "billing_state": TN,
        "billing_pincode": "638455",
        "branches": [
            {
                "name": "Distillery Unit",
                "gstin": "33AACCE4321M2Z7",
                "phones": ["9789044556"],
                "address_line1": "Bhavani Main Road",
                "city": "Bhavani",
                "state": TN,
                "pincode": "638301",
            },
        ],
    },
    {
        "name": "Coimbatore Foundry Works",
        "contact_person": "Mr. S. Balaji",
        "designation": "Plant Head",
        "phones": ["9894033445"],
        "emails": [],
        "gstin": "33AAGFC9876P1Z3",
        "billing_address_line1": "SIDCO Industrial Estate, Kurichi",
        "billing_city": "Coimbatore",
        "billing_state": TN,
        "billing_pincode": "641021",
        "branches": [],
    },
    {
        "name": "Namakkal Water Supply Board",
        "contact_person": "Er. M. Ravichandran",
        "designation": "Assistant Engineer",
        "phones": [],
        "emails": ["ae.namakkal@example.gov.in"],
        "gstin": "33AAAGN1111Q1Z6",
        "billing_address_line1": "Collectorate Campus",
        "billing_city": "Namakkal",
        "billing_state": TN,
        "billing_pincode": "637001",
        "branches": [],
    },
    {
        "name": "Hosur Auto Components",
        "contact_person": "Mr. V. Arun",
        "designation": "Utilities In-charge",
        "phones": ["9500011122"],
        "emails": ["utilities@hosurauto.example"],
        "gstin": "33AADCH7777R1Z1",
        "billing_address_line1": "Plot 88, SIPCOT Phase I",
        "billing_city": "Hosur",
        "billing_state": TN,
        "billing_pincode": "635126",
        "branches": [
            {
                "name": "Unit 2",
                "gstin": "33AADCH7777R2Z0",
                "contact_person": "Mr. D. Karthik",
                "address_line1": "SIPCOT Phase II",
                "city": "Hosur",
                "state": TN,
                "pincode": "635109",
            },
        ],
    },
]

SUPPLIERS: list[dict[str, Any]] = [
    {
        "name": "Deccan Pumps & Motors Ltd",
        "contact_person": "Mr. Nitin Kulkarni",
        "phones": ["9822012345"],
        "emails": ["sales@deccanpumps.example"],
        "gstin": "27AABCD1234E1Z2",
        "address_line1": "MIDC Bhosari, J Block",
        "city": "Pune",
        "state": "Maharashtra",
        "pincode": "411026",
        "branches": [
            {
                "name": "Chennai Depot",
                "gstin": "33AABCD1234E1Z0",
                "phones": ["9840055667"],
                "emails": ["chennai@deccanpumps.example"],
                "address_line1": "Ambattur Industrial Estate",
                "city": "Chennai",
                "state": TN,
                "pincode": "600058",
            },
        ],
    },
    {
        "name": "Kovai Couplings",
        "contact_person": "Mr. R. Ganesh",
        "phones": ["9443322110"],
        "emails": ["kovaicouplings@example.com"],
        "gstin": "33AAJFK2468L1Z4",
        "address_line1": "Ganapathy Industrial Area",
        "city": "Coimbatore",
        "state": TN,
        "pincode": "641006",
        "branches": [],
    },
    {
        "name": "Sri Murugan Fabricators",
        "contact_person": "Mr. P. Selvam",
        "phones": ["9787654321"],
        "emails": [],
        "gstin": "33ABCFS1357M1Z9",
        "address_line1": "Five Roads, Behind Bus Depot",
        "city": "Salem",
        "state": TN,
        "pincode": "636004",
        "branches": [],
    },
    {
        "name": "Precision Seals India",
        "contact_person": "Ms. Anjali Mehta",
        "phones": ["9898012345"],
        "emails": ["orders@precisionseals.example"],
        "gstin": "24AAECP8642N1Z7",
        "address_line1": "GIDC Vatva, Phase IV",
        "city": "Ahmedabad",
        "state": "Gujarat",
        "pincode": "382445",
        "branches": [
            {
                "name": "Coimbatore Branch",
                "gstin": "33AAECP8642N1Z1",
                "phones": ["9894012345"],
                "address_line1": "Avinashi Road, Peelamedu",
                "city": "Coimbatore",
                "state": TN,
                "pincode": "641004",
            },
        ],
    },
    {
        "name": "Southern Valves & Fittings",
        "contact_person": "Mr. J. Thomas",
        "phones": ["9446012345"],
        "emails": ["sales@southernvalves.example"],
        "gstin": "32AAGFS9753P1Z5",
        "address_line1": "Kalamassery Industrial Estate",
        "city": "Kochi",
        "state": "Kerala",
        "pincode": "683104",
        "branches": [],
    },
]

CATEGORIES = ["Pumps", "Motors", "Couplings", "Base Frames", "Seals", "Valves", "Spares"]

# (sku, name, model, category, supplier, hsn, unit, purchase Rs, sell Rs, opening stock)
# Stock is varied on purpose: plenty, low (5 or less, the low-stock line),
# and none at all, so the order and purchase order flows can be tried.
# No sample products: Inventory holds the real stock, imported from Tally
# (scripts/import_tally_stock.py).
PRODUCTS: list[tuple[str, str, str, str, str, str, str, int, int, int]] = []


def _exists(db: Session, model: Any, name: str) -> bool:
    return (
        db.execute(select(model.id).where(func.lower(model.name) == name.lower())).first()
        is not None
    )


def main() -> None:
    db = SessionLocal()
    added: dict[str, int] = {
        "customers": 0,
        "branches": 0,
        "suppliers": 0,
        "categories": 0,
        "products": 0,
    }
    try:
        actor = db.execute(select(User.id).order_by(User.id)).scalars().first()

        for c in CUSTOMERS:
            if _exists(db, Customer, c["name"]):
                continue
            body = {k: v for k, v in c.items() if k != "branches"}
            customer = customers.create_customer(db, CustomerCreate(**body))
            added["customers"] += 1
            for b in c["branches"]:
                customers.create_branch(db, customer.id, CustomerBranchCreate(**b))
                added["branches"] += 1

        for s in SUPPLIERS:
            if _exists(db, Supplier, s["name"]):
                continue
            body = {k: v for k, v in s.items() if k != "branches"}
            supplier, _ = suppliers.create_supplier(db, SupplierCreate(**body))
            added["suppliers"] += 1
            for b in s["branches"]:
                suppliers.create_branch(db, supplier.id, SupplierBranchCreate(**b))
                added["branches"] += 1

        for name in CATEGORIES:
            if not _exists(db, Category, name):
                categories.create_category(db, CategoryCreate(name=name))
                added["categories"] += 1

        def id_of(model: Any, name: str) -> int:
            return int(
                db.execute(
                    select(model.id).where(func.lower(model.name) == name.lower())
                ).scalar_one()
            )

        for sku, name, model, cat, sup, hsn, unit, cost, sell, qty in PRODUCTS:
            if db.execute(select(Product.id).where(Product.sku == sku)).first() is not None:
                continue
            products.create_product(
                db,
                ProductCreate(
                    sku=sku,
                    name=name,
                    model_number=model,
                    unit=unit,
                    hsn_code=hsn,
                    supplier_id=id_of(Supplier, sup),
                    category_id=id_of(Category, cat),
                    purchase_cost=cost * 100,
                    sell_price=sell * 100,
                    gst_rate_bp=1800,
                    opening_quantity=qty,
                ),
                actor_id=actor,
            )
            added["products"] += 1
    finally:
        db.close()
    print("Added: " + ", ".join(f"{n} {k}" for k, n in added.items()))


if __name__ == "__main__":
    main()
