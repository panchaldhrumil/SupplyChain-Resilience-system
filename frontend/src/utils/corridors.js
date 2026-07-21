// Shared corridor color/label helpers
export const CORRIDOR_LABELS = {
  hormuz:            'Strait of Hormuz',
  red_sea:           'Red Sea / Bab-el-Mandeb',
  suez:              'Suez Canal',
  cape_of_good_hope: 'Cape of Good Hope',
  russia_route:      'Russia / Black Sea',
  malacca:           'Malacca Strait',
  india_domestic:    'India Domestic',
};

export const LEVEL_COLORS = {
  red:   { ring: '#ef4444', bg: 'rgba(239,68,68,0.15)',   label: 'CRITICAL',  text: '#fca5a5' },
  amber: { ring: '#f59e0b', bg: 'rgba(245,158,11,0.15)',  label: 'ELEVATED',  text: '#fcd34d' },
  green: { ring: '#22c55e', bg: 'rgba(34,197,94,0.12)',   label: 'NOMINAL',   text: '#86efac' },
};

export const LEVEL_TW = {
  red:   'bg-red-900/40 border-red-500 text-red-300',
  amber: 'bg-amber-900/40 border-amber-500 text-amber-300',
  green: 'bg-green-900/30 border-green-600 text-green-300',
};

// Corridor polyline coordinates [lat, lng] pairs for Leaflet
export const CORRIDOR_PATHS = {
  hormuz:            [[26.57, 56.25], [24.5, 58.8]],   // water passage: Musandam↔Iran narrowest point → Gulf of Oman
  red_sea:           [[12.5, 43.3], [27.6, 34.6]],
  suez:              [[30.5, 32.3], [29.9, 32.6]],
  cape_of_good_hope: [[-34.4, 18.5], [-25.0, 15.0], [-10.0, 17.0]],
  russia_route:      [[59.5, 28.0], [55.0, 37.0], [43.0, 40.0]],
  malacca:           [[1.3, 103.8], [4.0, 100.5], [5.5, 98.0]],
};
