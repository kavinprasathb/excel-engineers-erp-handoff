"""Customers taken from the past offer letters in "3. Executed".

Run from the backend folder:

    uv run python -m scripts.import_offer_customers "D:/Excel Engg/3. Executed" --preview out.xlsx
    uv run python -m scripts.import_offer_customers "D:/Excel Engg/3. Executed" --apply

Every offer opens with the same header ("M/s. Kansai Nerolac Paints Ltd
ESQP 24-387 / Hosur, 17/10/2024 / Kind Attn.: Mr.Suresh"). The headers are
typed by hand and the same company is spelt several ways, so the list below
was put together by reading every header, not guessed by a matcher. The
script then checks the list against the letters before anything is saved:
each customer's (and branch's) name words must appear in an offer header in
every folder it cites, and its city in the header of at least one of them.
--apply refuses to run while any check fails. The few offers kept only as
PDF (pdf_also) were read by hand and are not re-checked.

What the letters hold, and so what is filled: name, city, state (from the
city), contact person, pin code where the header has one, and branches where
the letters name a plant, unit or site. They hold no customer GST number,
phone or email: the only GSTIN in them (33AAIFE2328P1Z9) and the mobile
9444915716 are Excel Engineers' own, and the other GSTIN found in a PDF is a
seal supplier's. Those fields are left blank and the customer shows "Needs
details" until completed.

--apply skips a customer whose name already exists (and fills only blank
fields of the existing SAIL record), so it is safe to rerun.
"""

import argparse
import glob
import os
import re
import sys
import zipfile
from typing import Any

from openpyxl import Workbook  # type: ignore[import-untyped]
from sqlalchemy import delete, func, select

from app.db import SessionLocal
from app.models import Customer, CustomerBranch

TN = "Tamil Nadu"
STATE = {"Hyderabad": "Telangana", "Bangalore": "Karnataka", "Puducherry": "Puducherry"}

# name, city, pin, contact, folders (offer numbers), check words, branches, flags
# A branch: (branch name, city, pin, contact, folders).
C: list[dict[str, Any]] = [
    dict(
        name="Kansai Nerolac Paints Ltd",
        city="Hosur",
        contact="Mr. Manikandan V G",
        src=["24-387", "25-058", "25-112", "25-235", "25-355", "25-402"],
        key="nerolac",
    ),
    dict(
        name="Paragon Pvt Ltd", city="", src=["25-001"], key="paragon", note="Letter gives no city."
    ),
    dict(
        name="Kallakurichi Co-op Sugar Mills Ltd I",
        city="Moongilthuraipattu",
        pin="605702",
        contact="Dy. Chief Engineer",
        src=["25-004", "25-074"],
        key="kal",
    ),
    dict(
        name="Brakes India Pvt Ltd",
        city="Sholinghur",
        contact="Mr. Jayakanthan R",
        src=["25-005", "25-190"],
        key="brakes",
        branches=[
            (
                "Foundry Division",
                "Sholinghur",
                "",
                "Mr. Arumugam",
                ["25-268", "25-278", "25-354", "25-376", "25-381", "25-425", "25-454"],
            ),
            (
                "Foundry Division Unit II",
                "Ranipet",
                "",
                "Mr. Jaganathan",
                ["25-093", "25-131", "25-146"],
            ),
            ("Foundry Unit 1", "Sholinghur", "", "", ["25-463"]),
        ],
    ),
    dict(name="TVS Fasteners", city="Hosur", src=["25-006"], key="tvs fast"),
    dict(
        name="Hy-Power Engineers",
        city="Bangalore",
        src=["25-006"],
        key="hy- power",
        note="Named on offer 25-006 R2 (TVS Fasteners enquiry).",
    ),
    dict(
        name="Inframat Alloys Pvt Ltd",
        city="Soolagiri",
        contact="Mr. Thowsif",
        src=["25-007"],
        key="inframat",
    ),
    dict(
        name="Suriyagiri Spinning Mills",
        city="Kumarapalayam",
        contact="Mr. Karupaiyah",
        src=["25-008"],
        key="suriyagiri",
    ),
    dict(
        name="MRF Limited",
        city="Arkonam",
        pin="631003",
        contact="Mr. Kumaran M S",
        address="Arkonam - Tiruttani Road, Ichiputhur",
        src=["25-009", "25-061"],
        key="mrf",
    ),
    dict(
        name="SAIL",
        city="Salem",
        pin="636013",
        contact="Mr. M. Narendran, AGM (CRM-Mech)",
        address="Salem Steel Plant",
        src=["25-011", "25-151", "25-183"],
        key="s",
        note="Steel Authority of India - Salem Steel Plant; existing customer, blanks filled.",
        pdf_also=["25-015"],
    ),
    dict(name="ABC Fruits Pvt Ltd", city="Krishnagiri", src=["25-020", "25-298"], key="abc"),
    dict(
        name="Chendhoor Murugan Yarn Tex India Pvt Ltd",
        city="Komarapalayam",
        src=["25-021", "25-052"],
        key="chendhoor",
    ),
    dict(name="Chendoor Murugan Textiles", city="Veppadai", src=["25-051"], key="chendoor"),
    dict(
        name="Chemplast Sanmar Ltd",
        city="Mettur",
        contact="Mr. Sakthivel",
        src=["25-056", "25-077", "25-159", "25-382"],
        key="chemplast",
        branches=[("Berigai", "Berigai", "", "", ["25-025", "25-026", "25-108", "25-410"])],
    ),
    dict(name="SSR", city="Chennai", src=["25-025"], key="ssr"),
    dict(
        name="Hindustan Unilever Ltd",
        city="Hosur",
        contact="Mr. Ranjith",
        src=["25-027", "25-177", "25-219"],
        key="unil",
    ),
    dict(
        name="Propel Industries Pvt Ltd",
        city="",
        contact="Mr. Vetri",
        src=["25-028"],
        key="propel",
        note="MP Site; letter gives no city.",
    ),
    dict(
        name="Rajshree Sugars Ltd",
        city="Gingee",
        contact="Mr. Karthikeyan",
        src=["25-031", "25-347"],
        key="rajshree",
        pdf_also=["25-240", "25-416"],
    ),
    dict(name="Meenakshi Dyeing", city="Salem", src=["25-034"], key="meenakshi"),
    dict(
        name="TVS Motor Company Ltd",
        city="Hosur",
        contact="Mr. Kannan",
        src=["25-038", "25-048"],
        key="tvs motor",
        pdf_also=["25-170"],
        branches=[("Plant I", "Hosur", "", "", ["25-040", "25-455"])],
    ),
    dict(
        name="Dharanidhara Spinning Mills",
        city="Kakapalayam",
        src=["25-042", "25-107", "25-499"],
        key="dharanid",
    ),
    dict(name="SJLT Spinning Mills", city="Namakkal", src=["25-045"], key="sjlt"),
    dict(name="Vijay Tradings", city="Erode", src=["25-049", "25-261", "25-353"], key="vijay"),
    dict(
        name="Sri Vela Smelters",
        city="Tiruchengode",
        contact="Mr. Ramesh",
        src=["25-062", "25-284", "25-475"],
        key="vela smelters",
    ),
    dict(
        name="Lucky Weaves Pvt Ltd",
        city="Tiruchengode",
        src=["25-065", "25-251"],
        key="lucky weaves",
    ),
    dict(
        name="India Cements Ltd",
        city="Sankari",
        src=["25-066", "25-120"],
        key="india cements",
        pdf_also=["25-016"],
    ),
    dict(
        name="Vaigai Agro Food", city="Namakkal", contact="Mr. Babu", src=["25-069"], key="vaigai"
    ),
    dict(
        name="Vellore Co-op Sugar Mill Ltd",
        city="Vellore",
        contact="Dy. Chief Engineer",
        src=["25-075"],
        key="vellore",
    ),
    dict(name="Sri Dev Agro Foods", city="Krishnagiri", src=["25-078"], key="dev agro"),
    dict(
        name="Raasia Leathers",
        city="Ranipet",
        src=["25-085"],
        key="raasia",
        note="25-085 says Hosur, 25-085 R1 says Ranipet; newest kept.",
    ),
    dict(
        name="Fastenex Pvt Ltd",
        city="Villupuram",
        src=["25-086"],
        key="fastenex",
        note="Letter is for Plant 2.",
    ),
    dict(
        name="ABI Showatech Pvt Ltd",
        city="Sholinghur",
        src=["25-096", "25-201", "25-365", "25-366", "25-421"],
        key="show",
    ),
    dict(name="Tata Electronics Pvt Ltd", city="Hosur", src=["25-097", "25-165"], key="tata"),
    dict(name="Sundaram Auto Components Ltd", city="Hosur", src=["25-100"], key="sundharam"),
    dict(name="Neilkamal Furnitures", city="Soolagiri", src=["25-102"], key="neilkamal"),
    dict(
        name="KMV Blue Metals", city="Cheyyar", contact="Mr. Jeyakumar", src=["25-104"], key="kmv"
    ),
    dict(
        name="Subramaniya Siva Co-op Sugar Mills Ltd",
        city="Gopalapuram",
        pin="636904",
        address="Alapuram, Pappireddipatti Taluk",
        src=["25-109", "25-119"],
        key="siva",
    ),
    dict(
        name="Bannari Amman Sugars Ltd",
        city="Thiruvannamalai",
        contact="Mr. Saravanan",
        src=["25-111", "25-361"],
        key="ba",
        pdf_also=["25-070", "25-283"],
        note="Unit 4.",
        branches=[("Unit 5", "Tirukoilur", "", "Mr. Tirumurugan", ["25-358"])],
    ),
    dict(
        name="GMP Weaving Mills Pvt Ltd",
        city="Tiruchengode",
        contact="Ms. Shanmugapriya",
        src=["25-115"],
        key="gmp",
    ),
    dict(
        name="Prabha Automotive Pvt Ltd",
        city="Hosur",
        src=["25-117", "25-144", "25-171"],
        key="prabha auto",
    ),
    dict(name="Prabha Engineering", city="Hosur", src=["25-226"], key="prabha eng"),
    dict(
        name="Coromandel International Cements Ltd",
        city="Ranipet",
        src=["25-121", "25-317"],
        key="coromandel",
    ),
    dict(name="Brightway Solutions", city="Chennai", src=["25-137"], key="brightway"),
    dict(
        name="Schaeffler India Ltd",
        city="Hosur",
        contact="Mr. Pattabiraman",
        src=["25-142", "25-195", "25-327"],
        key="schaeffler",
    ),
    dict(
        name="Thirumalaivasa Engineering Works",
        city="Salem",
        contact="Mr. Senthil",
        src=["25-151"],
        key="thirumalaivasa",
    ),
    dict(
        name="Hotel CJ Palazzio",
        city="Salem",
        src=["25-152", "25-153", "25-287", "25-318"],
        key="palazzio",
    ),
    dict(
        name="Chengalrayan Co-op Sugar Mills Ltd",
        city="Periyasevalai",
        pin="607209",
        src=["25-152"],
        key="chengalrayan",
    ),
    dict(name="Cyan Process Automation", city="Hyderabad", src=["25-155"], key="cyan"),
    dict(
        name="Green Resource Enterprises (GRE)",
        city="Salem",
        contact="Mr. Vijayakumar",
        src=["25-160", "25-206", "25-217"],
        key="gre",
    ),
    dict(
        name="Thirumalai Chemicals Ltd",
        city="Ranipet",
        contact="Mr. Ganesan / Mr. Logesh",
        src=["25-164", "25-484"],
        key="thirumalai chem",
    ),
    dict(
        name="Ultramarine & Pigments Ltd",
        city="Ranipet",
        contact="Mr. T. Rameshbabu",
        src=["25-172", "25-447"],
        key="ultramarine",
    ),
    dict(
        name="Sivasakthi Blue Metals",
        city="Thiruttani",
        src=["25-181"],
        key="sivasakthi",
        note="Propel site.",
    ),
    dict(
        name="S. P. Mani & Mohan Dairy (India) Pvt Ltd",
        city="Komarapalayam",
        src=["25-182"],
        key="mohan dairy",
    ),
    dict(name="BHEL", city="Udangudi", src=["25-185"], key="bhel"),
    dict(
        name="Ashok Leyland Ltd",
        city="Hosur",
        src=["25-189", "25-215", "25-362", "25-411"],
        key="ashok",
    ),
    dict(
        name="SS Engineers",
        city="Hosur",
        src=["25-215"],
        key="ss engineers",
        note="For Ashok Leyland (offer 25-215).",
    ),
    dict(
        name="SNR Foods",
        city="Srinivasapuram",
        contact="Mr. Prasad",
        src=["25-193"],
        key="snr",
        note="State not known for Srinivasapuram.",
    ),
    dict(name="Golden Spinning Mills Ltd", city="Valapadi", src=["25-194"], key="golden"),
    dict(name="Selvanayagi", city="Coimbatore", src=["25-197"], key="selvanayagi"),
    dict(name="Bio Plus", city="Hosur", src=["25-199"], key="bio plus"),
    dict(name="Sri Constructions", city="Namakkal", src=["25-208"], key="sri constructions"),
    dict(
        name="Sri Blue Metals", city="Salem", src=["25-133", "25-207", "25-350"], key="blue metals"
    ),
    dict(name="Pricol Precision Pvt Ltd", city="Hosur", src=["25-218"], key="pricol"),
    dict(name="Anitha Spinning Mills", city="Tiruchengode", src=["25-225"], key="anitha"),
    dict(name="Amudha Surabi Foods", city="Kaveripattinam", src=["25-227"], key="amudha"),
    dict(name="Sundardass Spinning Mills", city="Salem", src=["25-229"], key="sundardass"),
    dict(name="Wabtec", city="Hosur", src=["25-230"], key="wabtech"),
    dict(name="Thulasi Agencies", city="Puducherry", src=["25-231"], key="thulasi"),
    dict(name="Nandhi Fruits", city="Krishnagiri", src=["25-243"], key="nandhi"),
    dict(name="Shanmuga Hospital", city="Salem", src=["25-250"], key="shanmuga"),
    dict(name="Siby Solvent Extractions", city="Chinnasalem", src=["25-259"], key="siby"),
    dict(
        name="B&B Triple Wall Containers",
        city="Pochampalli",
        contact="Mr. Sanjay",
        src=["25-260"],
        key="b&b",
    ),
    dict(
        name="Konzept Engineers",
        city="",
        src=["25-267"],
        key="konzept",
        note="Letter gives no city.",
    ),
    dict(
        name="Pallava Textiles",
        city="Tiruchengode",
        src=["25-273", "25-487"],
        key="pallava",
        note="Unit 3.",
    ),
    dict(
        name="Fluid Technologies",
        city="",
        src=["25-281"],
        key="fluid",
        note="Letter gives no city.",
    ),
    dict(name="Faiveley Transport", city="Hosur", src=["25-282"], key="faively"),
    dict(name="Arogranite", city="Hosur", src=["25-295"], key="arogranite"),
    dict(name="GRB Dairy Foods Ltd", city="Hosur", src=["25-308", "25-330", "25-388"], key="grb"),
    dict(
        name="Cheyyar Co-op Sugar Mills",
        city="Cheyyar",
        contact="Dy. Chief Engineer",
        src=["25-309"],
        key="cheyyar",
    ),
    dict(name="Ecomax", city="Salem", src=["25-311"], key="ecomax", note="Varalakshmi site."),
    dict(
        name="Daack Vessels Pvt Ltd",
        city="Ranipet",
        contact="Mr. S. S. Ganesh",
        src=["25-314"],
        key="daack",
    ),
    dict(
        name="Malladi Drugs Ltd",
        city="Chennai",
        src=["25-494"],
        key="malladi",
        pdf_also=["25-480", "25-496"],
        branches=[("M3 Engg. Service", "Ranipet", "", "Mr. Kabilan S", ["25-320"])],
    ),
    dict(name="MST Smelters", city="Sholinghur", src=["25-324"], key="mst"),
    dict(
        name="Krafton Papers India Pvt Ltd",
        city="Soolagiri",
        src=["25-329", "25-377", "25-378"],
        key="krafton",
    ),
    dict(
        name="Thermax Ltd",
        city="",
        src=["25-339", "25-419"],
        key="thermax",
        note="Site work only; head office not in the letters.",
        branches=[
            ("Sundaram Fasteners site", "Villupuram", "", "", ["25-339"]),
            ("Varalakshmi site", "Salem", "", "", ["25-419"]),
        ],
    ),
    dict(
        name="Shri Varalakshmi Company",
        city="Salem",
        contact="Mr. Sarvesh",
        src=["25-348"],
        key="varalakshmi company",
    ),
    dict(
        name="Sri Varalakshmi Sago",
        city="Mallur",
        src=["25-373"],
        key="varalakshmi sago",
        pdf_also=["25-345"],
    ),
    dict(
        name="Lucky Yarn Tex India Pvt Ltd", city="Pallipalayam", src=["25-351"], key="lucky yarn"
    ),
    dict(name="Hatsun Agro Products Ltd", city="Dharapuram", src=["25-371", "25-400"], key="ha"),
    dict(
        name="JSW Steel Ltd",
        city="Mecheri",
        src=["25-398", "25-438"],
        key="jsw",
        note="GGBS plant; 25-398 says Salem, 25-438 says Mecheri (Salem district).",
    ),
    dict(name="Chips Company", city="Dharmapuri", src=["25-412"], key="chips"),
    dict(
        name="Noble Tech Industries Pvt Ltd",
        city="Uthiramerur",
        contact="Mr. Hariharan",
        src=["25-414"],
        key="noble",
    ),
    dict(name="Amirtha Sago", city="Attur", src=["25-421"], key="amirtha"),
    dict(
        name="Omni Active Pvt Ltd", city="Hosur", contact="Mr. Saranraj", src=["25-422"], key="omni"
    ),
    dict(name="CK Airtech", city="Hosur", src=["25-428"], key="ck airtech"),
    dict(
        name="MRK Co-op Sugar Mills Ltd",
        city="Sethiathoppu",
        contact="Mr. Senthilkumar (Cogen)",
        src=["25-451"],
        key="mrk",
    ),
    dict(
        name="Jagath Guru Textiles Ltd",
        city="Vellakoil",
        src=["25-452", "25-465"],
        key="jagath",
        pdf_also=["25-445"],
    ),
    dict(
        name="Pavithran Aseptic Fruits",
        city="Paiyur",
        src=["25-490"],
        key="pavithran",
        note="Paiyur, Krishnagiri.",
    ),
    dict(name="Selvam Trading", city="Namakkal", src=["25-500"], key="selvam"),
    dict(
        name="Indus TMT",
        city="",
        src=[],
        key="indus",
        pdf_also=["25-333"],
        note="PDF offer only; no city.",
    ),
    dict(
        name="Ion Exchange (India) Ltd",
        city="",
        src=[],
        key="ion",
        pdf_also=["25-461", "25-476"],
        note="PDF offers only; no city.",
    ),
]

# Letter headers spell a word differently from the name kept; what to look for.
SPELLING = {
    "Hosur": "hosur",
    "Tiruchengode": "tiruchengod|thiruchengod",
    "Sholinghur": "sholing",
    "Namakkal": "nam+ak+al",
    "Puducherry": "pondy",
    "Gopalapuram": "gopalapuram",
    "Kaveripattinam": "kaveripat",
    "Attur": "athur",
    "Thiruttani": "thirutani",
    "Udangudi": "udankudi",
    "Tirukoilur": "tirukovilur",
    "Thiruvannamalai": "th?iruvannamalai",
    "Komarapalayam": "komara?pa?layam",
    "Villupuram": "vill?upuram",
    "Soolagiri": "soo?l[ai]giri",
    "Coimbatore": "cbe",
    "Mecheri": "mecheri|salem",
}


def headers(folder: str, prefix: str) -> list[str]:
    """The first lines of every Word offer in the folders starting with `prefix`."""
    out = []
    for f in glob.glob(os.path.join(folder, glob.escape(prefix) + "*", "*.docx")):
        if os.path.basename(f).startswith("~$"):
            continue
        try:
            x = zipfile.ZipFile(f).read("word/document.xml").decode("utf8", "ignore")
        except (zipfile.BadZipFile, KeyError):
            continue
        t = re.sub(r"<[^>]+>", "", re.sub(r"</w:p>", "\n", x)).replace("&amp;", "&")
        lines = [" ".join(s.split()) for s in t.split("\n") if s.strip()]
        head = " ".join(lines[:6])
        if re.search(r"ESQ[A-Z]*", head):
            out.append(head.lower())
    return out


def check(folder: str) -> list[str]:
    """Check 1 and 2 of the module docstring; returns the problems found."""
    problems = []
    rows = [(c["name"], c["city"], c["key"], c["src"]) for c in C]
    rows += [
        (f"{c['name']} / {b[0]}", b[1], c["key"], b[4]) for c in C for b in c.get("branches", [])
    ]
    for name, city, key, src in rows:
        seen: list[str] = []
        for prefix in src:
            hs = headers(folder, prefix)
            if not any(key in h for h in hs):
                problems.append(f"{name}: '{key}' not in any offer header of {prefix}")
            seen += hs
        pattern = SPELLING.get(city, re.escape(city.lower()))
        if city and src and not any(re.search(pattern, h) for h in seen):
            problems.append(f"{name}: city {city} not in any of its offers {src}")
    return problems


def state_of(city: str) -> str:
    if not city or city == "Srinivasapuram":
        return ""
    return STATE.get(city, TN)


def preview(out: str) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Customers from offers"
    ws.append(
        [
            "Customer",
            "Branch",
            "City",
            "State",
            "Pin",
            "Address",
            "Contact",
            "GST",
            "Offers",
            "Note",
        ]
    )
    for c in C:
        ws.append(
            [
                c["name"],
                "",
                c["city"],
                state_of(c["city"]),
                c.get("pin", ""),
                c.get("address", ""),
                c.get("contact", ""),
                "",
                ", ".join(c["src"] + c.get("pdf_also", [])),
                c.get("note", ""),
            ]
        )
        for b in c.get("branches", []):
            ws.append(["", b[0], b[1], state_of(b[1]), b[2], "", b[3], "", ", ".join(b[4]), ""])
    for col, w in zip("ABCDEFGHIJ", [42, 26, 18, 13, 8, 34, 28, 8, 40, 50], strict=True):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "B2"
    wb.save(out)


def apply() -> None:
    db = SessionLocal()
    try:
        # The made-up sample customers go, unless something already uses them.
        for name in [
            "Kaveri Chemicals Pvt Ltd",
            "Salem Textile Processors",
            "Erode Sugars & Distilleries Ltd",
            "Coimbatore Foundry Works",
            "Namakkal Water Supply Board",
            "Hosur Auto Components",
        ]:
            sample = db.execute(select(Customer.id).where(Customer.name == name)).scalar()
            if sample is not None:
                db.execute(delete(CustomerBranch).where(CustomerBranch.customer_id == sample))
                db.execute(delete(Customer).where(Customer.id == sample))
        db.commit()
        added = filled = skipped = branches = 0
        for c in C:
            note = c.get("note", "")
            offers = ", ".join(c["src"] + c.get("pdf_also", []))
            values = dict(
                contact_person=c.get("contact", ""),
                billing_address_line1=c.get("address", ""),
                billing_city=c["city"],
                billing_state=state_of(c["city"]),
                billing_pincode=c.get("pin", ""),
            )
            existing = db.execute(
                select(Customer).where(func.lower(Customer.name) == c["name"].lower())
            ).scalar_one_or_none()
            if existing is not None:
                if c["name"] != "SAIL":
                    skipped += 1
                    continue
                # Only blanks are filled; nothing typed in the app is overwritten.
                for k, v in values.items():
                    if v and not getattr(existing, k):
                        setattr(existing, k, v)
                customer = existing
                filled += 1
            else:
                # Saved without GST (the letters have none): "Needs details" in the app.
                customer = Customer(
                    name=c["name"],
                    **values,
                    notes=(
                        f"From offers {offers}. "
                        + (note + " " if note else "")
                        + "Complete GST, address and pin code."
                    ),
                )
                db.add(customer)
                added += 1
            db.flush()
            db.refresh(customer)
            for bname, city, pin, contact, _ in c.get("branches", []):
                if any(
                    b.name == bname
                    for b in db.execute(
                        select(CustomerBranch).where(CustomerBranch.customer_id == customer.id)
                    ).scalars()
                ):
                    continue
                customer.branch_seq += 1
                db.add(
                    CustomerBranch(
                        customer_id=customer.id,
                        seq=customer.branch_seq,
                        code=f"{customer.code}-BR{customer.branch_seq:02d}",
                        name=bname,
                        contact_person=contact,
                        city=city,
                        state=state_of(city),
                        pincode=pin,
                    )
                )
                branches += 1
            db.commit()
        print(
            f"Added {added} customers and {branches} branches; filled blanks on {filled}; "
            f"skipped {skipped} already there."
        )
    finally:
        db.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--preview", metavar="OUT.xlsx")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    problems = check(a.folder)
    n_branches = sum(len(c.get("branches", [])) for c in C)
    print(f"{len(C)} customers, {n_branches} branches; {len(problems)} check problems")
    for p in problems:
        print("  ", p)
    if a.preview:
        preview(a.preview)
        print("preview written to", a.preview)
    if a.apply:
        if problems:
            sys.exit("Not applied: fix the problems above first.")
        apply()


if __name__ == "__main__":
    main()
