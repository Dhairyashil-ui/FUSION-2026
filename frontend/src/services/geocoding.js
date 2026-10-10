/**
 * Geocoding dictionary and helper for GeoAI locations
 */

const KNOWN_LOCATIONS = {
  mumbai: {
    name: 'Mumbai, Maharashtra, India',
    center: [19.076, 72.8777],
    zoom: 12,
    bbox: [
      [18.892, 72.775],
      [19.271, 72.986]
    ]
  },
  pune: {
    name: 'Pune, Maharashtra, India',
    center: [18.5204, 73.8567],
    zoom: 12,
    bbox: [
      [18.420, 73.740],
      [18.620, 73.970]
    ]
  },
  bengaluru: {
    name: 'Bengaluru, Karnataka, India',
    center: [12.9716, 77.5946],
    zoom: 12,
    bbox: [
      [12.834, 77.460],
      [13.139, 77.749]
    ]
  },
  bangalore: {
    name: 'Bengaluru, Karnataka, India',
    center: [12.9716, 77.5946],
    zoom: 12,
    bbox: [
      [12.834, 77.460],
      [13.139, 77.749]
    ]
  },
  delhi: {
    name: 'Delhi, India',
    center: [28.6139, 77.2090],
    zoom: 11,
    bbox: [
      [28.404, 76.840],
      [28.883, 77.348]
    ]
  },
  hyderabad: {
    name: 'Hyderabad, Telangana, India',
    center: [17.3850, 78.4867],
    zoom: 12,
    bbox: [
      [17.260, 78.330],
      [17.520, 78.620]
    ]
  },
  california: {
    name: 'California, USA',
    center: [36.7783, -119.4179],
    zoom: 6,
    bbox: [
      [32.534, -124.409],
      [42.009, -114.131]
    ]
  },
  tokyo: {
    name: 'Tokyo, Japan',
    center: [35.6762, 139.6503],
    zoom: 11,
    bbox: [
      [35.501, 139.560],
      [35.817, 139.919]
    ]
  },
  london: {
    name: 'London, United Kingdom',
    center: [51.5074, -0.1278],
    zoom: 12,
    bbox: [
      [51.286, -0.510],
      [51.691, 0.334]
    ]
  },
  newyork: {
    name: 'New York, USA',
    center: [40.7128, -74.0060],
    zoom: 11,
    bbox: [
      [40.496, -74.259],
      [40.917, -73.700]
    ]
  }
}

export function findLocation(queryOrName) {
  if (!queryOrName) return null
  const lower = queryOrName.toLowerCase().replace(/[^a-z0-9]/g, '')
  
  for (const [key, loc] of Object.entries(KNOWN_LOCATIONS)) {
    if (lower.includes(key)) {
      return loc
    }
  }

  // Check if coordinates format e.g. "19.07, 72.87"
  const coordsMatch = queryOrName.match(/(-?\d+\.?\d*)[,\s]+(-?\d+\.?\d*)/)
  if (coordsMatch) {
    const lat = parseFloat(coordsMatch[1])
    const lng = parseFloat(coordsMatch[2])
    if (!isNaN(lat) && !isNaN(lng) && Math.abs(lat) <= 90 && Math.abs(lng) <= 180) {
      const delta = 0.05
      return {
        name: `Lat: ${lat.toFixed(4)}, Lng: ${lng.toFixed(4)}`,
        center: [lat, lng],
        zoom: 13,
        bbox: [
          [lat - delta, lng - delta],
          [lat + delta, lng + delta]
        ]
      }
    }
  }

  return null
}
