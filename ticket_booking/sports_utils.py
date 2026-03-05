import requests
import random

SPORT_IMAGES = {
    "Cricket": [
        "https://images.unsplash.com/photo-1540747913346-19e32dc3e97e?q=80&w=600&auto=format&fit=crop", 
        "https://images.unsplash.com/photo-1531415074968-036ba1b575da?q=80&w=600&auto=format&fit=crop", # Backup just in case
        "https://images.unsplash.com/photo-1540747913346-19e32dc3e97e?q=80&w=600&auto=format&fit=crop", # Backup just in case
        "https://images.unsplash.com/photo-1582885934664-98ceb852a32c?q=80&w=600&auto=format&fit=crop" # 2Qg1WmFXC8I direct image replacement
    ],
    "Football": [
        "https://images.unsplash.com/photo-1505305976870-c0be1cd39939?q=80&w=1470&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1546418172-f9c9b6ab0c4a?q=80&w=735&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1581588535512-4dbe198fbbee?q=80&w=1325&auto=format&fit=crop"
    ],
    "Basketball": [
        "https://images.unsplash.com/photo-1519861531473-920026073336?q=80&w=1472&auto=format&fit=crop", # Premium fallback
        "https://images.unsplash.com/photo-1677031058176-000425075d04?q=80&w=687&auto=format&fit=crop"
    ],
    "Tennis": [
        "https://images.unsplash.com/photo-1595435934249-5df7ed86e1c0?q=80&w=1470&auto=format&fit=crop", # Premium fallback
        "https://images.unsplash.com/photo-1606151595697-648a9a840cdc?q=80&w=687&auto=format&fit=crop"
    ]
}

def get_image_for_sport(sport):
    # Some of the provided "premium_photo" URLs might block hotlinking, so I added some robust standard fallbacks above.
    # The standard photo URLs provided (e.g., photo-15053059...) will work perfectly.
    images = SPORT_IMAGES.get(sport, SPORT_IMAGES["Football"]) # Fallback to football if unknown sport
    return random.choice(images)

def generate_mock_turfs(location_name, base_lat, base_lon):
    """Helper to generate a realistic list of turfs when OSM APIs fail or return 0 results."""
    turfs = []
    mock_names = ["Arena 36", "Kickoff Pitch", "The Dugout", "Urban Sports City", "AstroPark", "ProPlay Turf", "Velocity Sports", "Lions Den"]
    for i in range(8):
        sport = random.choice(['Football', 'Cricket', 'Tennis', 'Basketball'])
        turfs.append({
            "id": f"mock_fb_{i}",
            "name": f"{random.choice(mock_names)} {sport}",
            "sport": sport,
            "lat": base_lat + random.uniform(-0.02, 0.02),
            "lon": base_lon + random.uniform(-0.02, 0.02),
            "location": location_name, 
            "image_url": get_image_for_sport(sport),
            "rating": round(random.uniform(3.8, 5.0), 1),
            "distance": f"~{round(random.uniform(0.5, 5.0), 1)} Kms",
            "price_per_hour": random.choice([800, 1000, 1200, 1500, 2000])
        })
    return turfs

def get_turfs_from_osm(location="Mumbai"):
    # Step 1: Geocode the location using Nominatim
    geocode_url = "https://nominatim.openstreetmap.org/search"
    geocode_params = {
        'q': f"{location}, Maharashtra, India", # Scope it a bit to India/MH for better hits if just "Borivali"
        'format': 'json',
        'limit': 1
    }
    headers = {
        'User-Agent': 'FilmingoApp/1.0 (development)'
    }
    try:
        # Step 1: Geocode the location using Nominatim
        geo_resp = requests.get(geocode_url, params=geocode_params, headers=headers, timeout=10)
        geo_resp.raise_for_status()
        geo_data = geo_resp.json()
        
        if not geo_data:
            print(f"Location not found via Nominatim: {location}")
            return generate_mock_turfs(location, 19.0760, 72.8777) # Default Mumbai coords if totally not found
            
        lat = float(geo_data[0]['lat'])
        lon = float(geo_data[0]['lon'])
        display_name = location.title()
        
        # Step 2: Query Overpass within a roughly 15km bounding box around the coords
        lat_min, lat_max = lat - 0.15, lat + 0.15
        lon_min, lon_max = lon - 0.15, lon + 0.15
        
        query = f"""
        [out:json];
        (
          node["leisure"="pitch"]["name"]({lat_min},{lon_min},{lat_max},{lon_max});
          way["leisure"="pitch"]["name"]({lat_min},{lon_min},{lat_max},{lon_max});
        );
        out center 15;
        """
        url = "http://overpass-api.de/api/interpreter"
        
        # Use headers to avoid 403 blocks
        resp = requests.post(url, data={'data': query}, headers=headers, timeout=15)
        resp.raise_for_status()
        elements = resp.json().get('elements', [])
        
        if not elements:
            print(f"No OSM data found for {location}, falling back to simulated data.")
            return generate_mock_turfs(display_name, lat, lon)
            
        turfs = []
        for el in elements:
            tags = el.get('tags', {})
            sport = tags.get('sport', 'multisport').capitalize()
            if sport == 'Soccer':
                sport = 'Football'
                
            name = tags.get('name', 'Local Turf')
            
            # For ways with 'out center', coords are in the 'center' field
            p_lat = el.get('lat') or (el.get('center', {}).get('lat'))
            p_lon = el.get('lon') or (el.get('center', {}).get('lon'))
            
            turfs.append({
                "id": el.get('id'),
                "name": name,
                "sport": sport,
                "lat": p_lat,
                "lon": p_lon,
                "location": display_name, 
                "image_url": get_image_for_sport(sport),
                "rating": round(random.uniform(3.5, 5.0), 1),
                "distance": f"~{round(random.uniform(0.5, 8.0), 1)} Kms",
                "price_per_hour": random.choice([800, 1000, 1200, 1500, 2000])
            })
            
        random.shuffle(turfs)
        return turfs
        
    except (requests.exceptions.RequestException, ValueError) as e:
        print(f"OSM/Nominatim API Error: {e}. Falling back to mock data.")
        # If geocoding or Overpass completely fails (e.g. rate limit resulting in HTML response), 
        # fallback to generating mock turfs using approximate Mumbai coordinates to keep UI functional.
        return generate_mock_turfs(location.capitalize(), 19.0760, 72.8777)

def get_turf_details(turf_id):
    """
    Returns mock detailed information for a specific turf ID.
    In a real application with a DB, this would query the DB for the Turf object and its relations.
    Here we provide consistent hydration data for the frontend UI.
    """
    return {
        "id": turf_id,
        "timings": "5:00 pm - 1:00 am",
        "highlights": [
            "Rental Equipment Available"
        ],
        "amenities": [
            "Changing Room", 
            "Drinking Water", 
            "First Aid", 
            "Flood Lights", 
            "Parking", 
            "Washroom"
        ],
        "rules": [
            "Arrive min. 10mins before booking time"
        ]
    }
