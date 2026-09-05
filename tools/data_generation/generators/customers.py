"""
Customer Generator — Step 9

Generates 500 customers, each linked to an existing merchant.
Output: data/raw/synthetic/customers.jsonl
"""

import json
import os
import random

random.seed(42)

# ── Indian Name Components ───────────────────────────────────────────────────

FIRST_NAMES = [
    "Aarav", "Aditi", "Aditya", "Akshay", "Amit", "Ananya", "Anita", "Anjali",
    "Arjun", "Arun", "Bharti", "Chandan", "Deepak", "Devi", "Dhruv", "Divya",
    "Gaurav", "Geeta", "Harsh", "Isha", "Jaya", "Karan", "Kavita", "Krishna",
    "Lakshmi", "Manish", "Meera", "Mohan", "Nandini", "Neha", "Nikhil", "Nisha",
    "Pooja", "Pradeep", "Priya", "Rahul", "Raj", "Rajesh", "Rakesh", "Ravi",
    "Rohit", "Sachin", "Sandeep", "Sanjay", "Sapna", "Seema", "Shivani", "Shruti",
    "Siddharth", "Simran", "Sneha", "Sonu", "Sunil", "Sunita", "Suresh", "Swati",
    "Tanvi", "Usha", "Varun", "Vijay", "Vikram", "Vinod", "Vivek", "Yash",
]

LAST_NAMES = [
    "Agarwal", "Bansal", "Bhatia", "Chauhan", "Chopra", "Das", "Deshmukh",
    "Dutta", "Garg", "Goyal", "Gupta", "Iyer", "Jain", "Joshi", "Kapoor",
    "Khan", "Kumar", "Malhotra", "Mehta", "Mishra", "Mukherjee", "Nair",
    "Patel", "Patil", "Pillai", "Rao", "Reddy", "Saxena", "Sharma", "Singh",
    "Sinha", "Srivastava", "Thakur", "Tiwari", "Verma", "Yadav",
]

CITIES_BY_STATE = {
    "Maharashtra": ["Mumbai", "Pune", "Nagpur", "Thane", "Nashik"],
    "Karnataka": ["Bangalore", "Mysore", "Hubli", "Mangalore", "Belgaum"],
    "Delhi": ["New Delhi", "Dwarka", "Rohini", "Saket", "Janakpuri"],
    "Tamil Nadu": ["Chennai", "Coimbatore", "Madurai", "Salem", "Tiruchirappalli"],
    "Gujarat": ["Ahmedabad", "Surat", "Vadodara", "Rajkot", "Gandhinagar"],
    "Uttar Pradesh": ["Lucknow", "Noida", "Kanpur", "Agra", "Varanasi"],
    "Rajasthan": ["Jaipur", "Jodhpur", "Udaipur", "Kota", "Ajmer"],
    "West Bengal": ["Kolkata", "Howrah", "Durgapur", "Siliguri", "Asansol"],
    "Telangana": ["Hyderabad", "Warangal", "Nizamabad", "Karimnagar"],
    "Kerala": ["Kochi", "Thiruvananthapuram", "Kozhikode", "Thrissur"],
}

STATES = list(CITIES_BY_STATE.keys())

EMAIL_DOMAINS = [
    "gmail.com", "yahoo.com", "outlook.com", "hotmail.com",
    "rediffmail.com", "protonmail.com",
]


def generate_customers(merchants: list, output_dir: str, count: int = 500) -> list:
    """
    Generate customer records linked to existing merchants.
    
    Args:
        merchants: List of merchant dicts
        output_dir: Directory to write customers.jsonl
        count: Number of customers to generate
    
    Returns:
        List of customer dicts
    """
    customers = []
    
    for i in range(1, count + 1):
        # Assign to a random merchant
        merchant = random.choice(merchants)
        
        first_name = random.choice(FIRST_NAMES)
        last_name = random.choice(LAST_NAMES)
        full_name = f"{first_name} {last_name}"
        
        # Pick a state and city
        state = random.choice(STATES)
        city = random.choice(CITIES_BY_STATE[state])
        
        # Generate email
        email_user = f"{first_name.lower()}.{last_name.lower()}{random.randint(1, 999)}"
        email = f"{email_user}@{random.choice(EMAIL_DOMAINS)}"
        
        # Generate phone (Indian mobile: starts with 6-9)
        phone = f"+91{random.choice(['6','7','8','9'])}{random.randint(100000000, 999999999)}"
        
        customer = {
            "customer_id": f"CUS_{i:06d}",
            "merchant_id": merchant["merchant_id"],
            "name": full_name,
            "email": email,
            "phone": phone,
            "city": city,
            "state": state,
        }
        customers.append(customer)
    
    # Write to JSONL
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "customers.jsonl")
    with open(output_path, "w", encoding="utf-8") as f:
        for c in customers:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    
    print(f"✓ Generated {len(customers)} customers → {output_path}")
    return customers


if __name__ == "__main__":
    # Load merchants first
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    data_dir = os.path.join(base_dir, "data", "raw", "synthetic")
    
    merchants_path = os.path.join(data_dir, "merchants.jsonl")
    with open(merchants_path, "r") as f:
        merchants = [json.loads(line) for line in f]
    
    generate_customers(merchants, data_dir)
