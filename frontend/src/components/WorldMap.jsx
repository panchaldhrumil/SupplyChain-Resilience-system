// WorldMap — Leaflet map with corridor polylines colored by risk level
// Includes: floating legend, corridor name labels via DivIcon, hover tooltips
// Includes: India real markers — refineries, SPR sites, crude ports (real coordinates, static)
import { Fragment, useEffect, useMemo, useState } from 'react';
import { MapContainer, TileLayer, Polyline, Tooltip, CircleMarker, Marker, ZoomControl, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { CORRIDOR_LABELS, CORRIDOR_PATHS } from '../utils/corridors';

const LEVEL_HEX   = { red: '#ef4444', amber: '#f59e0b', green: '#22c55e' };
const LEVEL_LABEL = { red: 'HIGH', amber: 'ELEVATED', green: 'NOMINAL' };

// Centroid for label + tooltip anchor per corridor
const CORRIDOR_CENTERS = {
  hormuz:            [26.57, 56.25], // actual water channel — narrowest passage between Iran (N) and Musandam/Oman (S)
  red_sea:           [18.5,  41.5],
  suez:              [30.5,  32.2],
  cape_of_good_hope: [-23.0, 15.0],
  russia_route:      [47.0,  33.5],
  malacca:           [2.5,  102.0],
};

// Label offset (lat°, lng°) from the centre dot.
// Each label is placed at center+offset so text lands in open sea/clear sky,
// away from: the centre dot itself, India's landmass, and neighbouring labels.
// Verified at default zoom 3 (center=[20,60], 1°≈5.7 px at equator).
const LABEL_OFFSET = {
  hormuz:            [+4.0,  -5.0],  // [30, 52] → north of strait, over southern Iran
  red_sea:           [-2.0,  -6.0],  // [16.5, 35.5] → west, over open Red Sea/Sudan coast
  suez:              [+3.0,  -4.0],  // [33.5, 28.2] → north-west into Eastern Mediterranean
  cape_of_good_hope: [-4.0,  -2.0],  // [-27, 13] → south into South Atlantic
  russia_route:      [+4.0,  -5.0],  // [51, 28.5] → north into Romania/Moldova
  malacca:           [-3.0,  +2.0],  // [-0.5, 104] → south into Java Sea
};

// ─────────────────────────────────────────────────────────────────────────────
// India infrastructure markers — real public coordinates, static reference data
// ─────────────────────────────────────────────────────────────────────────────
const INDIA_REFINERIES = [
  { id: 'jamnagar_reliance', name: 'Jamnagar (Reliance)',    lat: 22.4276, lng: 69.8660, type: 'refinery' },
  { id: 'vadinar_nayara',    name: 'Vadinar (Nayara/Rosneft)', lat: 22.4344, lng: 69.7126, type: 'refinery' },
  { id: 'kochi_bpcl',        name: 'Kochi (BPCL)',           lat: 9.9576,  lng: 76.3601, type: 'refinery' },
  { id: 'mangalore_mrpl',    name: 'Mangalore (MRPL)',        lat: 12.9904, lng: 74.8466, type: 'refinery' },
  { id: 'paradip_iocl',      name: 'Paradip (IOCL)',          lat: 20.2705, lng: 86.6853, type: 'refinery' },
  { id: 'vizag_hpcl',        name: 'Visakhapatnam (HPCL)',    lat: 17.6974, lng: 83.2505, type: 'refinery' },
  { id: 'mumbai_hpcl',       name: 'Mumbai (HPCL/BPCL)',      lat: 18.9902, lng: 72.8573, type: 'refinery' },
];

const INDIA_SPR_SITES = [
  { id: 'spr_vizag',     name: 'SPR — Visakhapatnam (ISPRL)', lat: 17.6918, lng: 83.2522, type: 'spr' },
  { id: 'spr_mangaluru', name: 'SPR — Mangaluru (ISPRL)',     lat: 12.9168, lng: 74.8872, type: 'spr' },
  { id: 'spr_padur',     name: 'SPR — Padur (ISPRL)',         lat: 13.2250, lng: 74.7925, type: 'spr' },
];

const INDIA_CRUDE_PORTS = [
  { id: 'port_vadinar',  name: 'Vadinar (crude terminal)',   lat: 22.4439, lng: 69.7042, type: 'port' },
  { id: 'port_sikka',    name: 'Sikka (crude terminal)',     lat: 22.4320, lng: 69.8420, type: 'port' },
  { id: 'port_kandla',   name: 'Kandla Port',                lat: 23.0039, lng: 70.2189, type: 'port' },
  { id: 'port_paradip',  name: 'Paradip Port',               lat: 20.2580, lng: 86.7020, type: 'port' },
  { id: 'port_vizag',    name: 'Vizag Port (Visakhapatnam)', lat: 17.6890, lng: 83.2980, type: 'port' },
  { id: 'port_kochi',    name: 'Kochi Port (Cochin)',        lat: 9.9670,  lng: 76.2480, type: 'port' },
];

// ─────────────────────────────────────────────────────────────────────────────
// Icon factories
// ─────────────────────────────────────────────────────────────────────────────
function makeLabelIcon(label, color) {
  return L.divIcon({
    html: `<div style="
      font-family: Inter, sans-serif;
      font-size: 10px;
      font-weight: 700;
      color: ${color};
      white-space: nowrap;
      text-shadow: 0 0 6px #000, 0 0 12px #000;
      letter-spacing: 0.05em;
      pointer-events: none;
    ">${label.toUpperCase()}</div>`,
    className: '',
    iconAnchor: [-12, -8], // Shift 12px right, 8px down relative to center dot
  });
}

function makeInfraIcon(type) {
  const sym = { refinery: '🏭', spr: '🛢️', port: '⚓' }[type] || '📍';
  return L.divIcon({
    html: `<div style="font-size:15px;line-height:1;text-shadow:0 0 5px #000;">${sym}</div>`,
    className: '',
    iconAnchor: [8, 8],
    iconSize: [16, 16],
  });
}

// Cluster badge shown when several infra markers overlap at low zoom
function makeClusterIcon(group) {
  const count = group.length;
  const types = [...new Set(group.map(m => m.type))];
  const sym = types.map(t => ({ refinery: '🏭', spr: '🛢️', port: '⚓' }[t] || '📍')).join('');
  return L.divIcon({
    html: `<div style="
      background:rgba(10,14,26,0.93);
      border:1.5px solid #334155;
      border-radius:50%;
      width:34px;height:34px;
      display:flex;flex-direction:column;
      align-items:center;justify-content:center;
      box-shadow:0 0 10px rgba(0,0,0,0.7),0 0 0 2px rgba(251,191,36,0.22);
    "><span style="font-size:10px;line-height:1.1;">${sym.slice(0, 2)}</span
    ><span style="color:#fbbf24;font-weight:700;font-family:Inter,sans-serif;font-size:10px;line-height:1.1;">${count}</span></div>`,
    className: '',
    iconAnchor: [17, 17],
    iconSize: [34, 34],
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// Floating legend
// ─────────────────────────────────────────────────────────────────────────────
function MapLegend({ showInfra }) {
  return (
    <div style={{
      position: 'absolute', bottom: 28, left: 12, zIndex: 1000,
      background: 'rgba(10,14,26,0.88)',
      border: '1px solid #1f2d45',
      borderRadius: 8,
      padding: '8px 12px',
      backdropFilter: 'blur(6px)',
      fontSize: 11,
      lineHeight: 1.8,
      pointerEvents: 'none',
    }}>
      <div style={{ fontWeight: 700, color: '#94a3b8', marginBottom: 4, letterSpacing: '0.06em', fontSize: 10 }}>
        CORRIDOR RISK
      </div>
      {[['red', '≥ 66 — High'],['amber', '≥ 33 — Elevated'],['green', '< 33 — Nominal']].map(([lvl, txt]) => (
        <div key={lvl} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div style={{ width: 10, height: 10, borderRadius: 2, background: LEVEL_HEX[lvl], flexShrink: 0 }} />
          <span style={{ color: '#cbd5e1' }}>{txt}</span>
        </div>
      ))}
      {showInfra && (
        <>
          <div style={{ marginTop: 6, borderTop: '1px solid #1f2d45', paddingTop: 4, color: '#94a3b8', fontWeight: 700, fontSize: 10, letterSpacing: '0.05em' }}>
            INDIA INFRASTRUCTURE
          </div>
          {[['🏭', 'Refineries'], ['🛢️', 'SPR Sites'], ['⚓', 'Crude Ports']].map(([sym, lbl]) => (
            <div key={lbl} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
              <span style={{ fontSize: 12 }}>{sym}</span>
              <span style={{ color: '#94a3b8' }}>{lbl}</span>
            </div>
          ))}
        </>
      )}
      <div style={{ marginTop: 6, borderTop: '1px solid #1f2d45', paddingTop: 4, color: '#475569', fontSize: 10 }}>
        Hover corridor for score + headline
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// InfraLayer — zoom-aware clustering for India infrastructure markers
// Must be a direct child of <MapContainer> to access the Leaflet map context.
// At zoom < 5  → greedy 25-px-radius clusters (count badge + tooltip list).
// At zoom ≥ 5  → every marker rendered individually at its real lat/lng.
// ─────────────────────────────────────────────────────────────────────────────
function InfraLayer({ sites, showInfra }) {
  const [zoom, setZoom] = useState(3);
  useMapEvents({ zoomend: (e) => setZoom(e.target.getZoom()) });

  if (!showInfra) return null;

  const INDIVIDUAL_ZOOM = 5; // separate all icons at this zoom and above

  const renderSingle = (site) => (
    <Marker key={site.id} position={[site.lat, site.lng]} icon={makeInfraIcon(site.type)}>
      <Tooltip direction="top" offset={[0, -6]}>
        <div style={{ fontFamily: 'Inter, sans-serif', fontSize: 11 }}>
          <strong>{site.name}</strong>
          <div style={{ color: '#64748b', fontSize: 10 }}>
            {site.type === 'spr' ? 'Strategic Petroleum Reserve'
             : site.type === 'refinery' ? 'Oil Refinery' : 'Crude Import Port'}
          </div>
          <div style={{ color: '#475569', fontSize: 9 }}>Real coordinates · Static reference data</div>
        </div>
      </Tooltip>
    </Marker>
  );

  if (zoom >= INDIVIDUAL_ZOOM) {
    return <>{sites.map(renderSingle)}</>;
  }

  // ── Cluster: group markers within a ~25-px radius at the current zoom ──────
  // Convert 25 px → equivalent degrees so we can compare raw lat/lng without
  // projecting every point (accurate enough at these zoom levels).
  const pxPerDeg = Math.pow(2, zoom) * 256 / 360;
  const degThreshold = 25 / pxPerDeg;

  const assigned = new Set();
  const clusters = [];
  sites.forEach((site, i) => {
    if (assigned.has(i)) return;
    const group = [site];
    assigned.add(i);
    sites.forEach((other, j) => {
      if (assigned.has(j)) return;
      const cosLat = Math.cos(site.lat * Math.PI / 180);
      if (
        Math.abs(site.lat - other.lat) < degThreshold &&
        Math.abs(site.lng - other.lng) * cosLat < degThreshold
      ) {
        group.push(other);
        assigned.add(j);
      }
    });
    clusters.push(group);
  });

  return (
    <>
      {clusters.map((group, idx) => {
        const lat = group.reduce((s, m) => s + m.lat, 0) / group.length;
        const lng = group.reduce((s, m) => s + m.lng, 0) / group.length;

        if (group.length === 1) return renderSingle(group[0]);

        return (
          <Marker key={`cluster-${idx}`} position={[lat, lng]} icon={makeClusterIcon(group)}>
            <Tooltip direction="top" offset={[0, -10]}>
              <div style={{ fontFamily: 'Inter, sans-serif', fontSize: 11 }}>
                <strong style={{ color: '#fbbf24' }}>{group.length} infrastructure sites</strong>
                <div style={{ marginTop: 4 }}>
                  {group.map(m => (
                    <div key={m.id} style={{ color: '#cbd5e1', fontSize: 10 }}>{m.name}</div>
                  ))}
                </div>
                <div style={{ color: '#475569', fontSize: 9, marginTop: 4, borderTop: '1px solid #1f2d45', paddingTop: 3 }}>
                  Zoom to level 5+ to see individual sites
                </div>
              </div>
            </Tooltip>
          </Marker>
        );
      })}
    </>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main component
// ─────────────────────────────────────────────────────────────────────────────
export default function WorldMap({ corridors = [], pipelineTs, vesselEstimate = null, vesselNote = '' }) {
  // Stable key: prevents "Map container is being reused by another instance"
  // error in React 19 Strict Mode (react-leaflet v5 known issue).
  const mapKey = useMemo(() => `worldmap-${Date.now()}`, []);
  const [showInfra, setShowInfra] = useState(true);
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    setIsReady(true);
  }, []);

  const lookup = {};
  corridors.forEach(c => { lookup[c.corridor] = c; });
  const noData = corridors.length === 0;

  const allInfra = [...INDIA_REFINERIES, ...INDIA_SPR_SITES, ...INDIA_CRUDE_PORTS];

  return (
    <div style={{ position: 'relative', height: '100%', width: '100%' }}>
      {/* Infrastructure toggle button */}
      <button
        onClick={() => setShowInfra(v => !v)}
        title="Toggle India infrastructure markers"
        style={{
          position: 'absolute', top: 8, right: 8, zIndex: 1000,
          background: 'rgba(10,14,26,0.85)', border: '1px solid #1f2d45',
          borderRadius: 5, padding: '3px 8px', color: '#94a3b8',
          fontSize: 10, cursor: 'pointer', fontFamily: 'Inter, sans-serif',
          letterSpacing: '0.04em', userSelect: 'none',
        }}
      >
        {showInfra ? '🏭 Hide Infra' : '🏭 Show Infra'}
      </button>

      <div style={{
        position: 'absolute', top: 8, left: 12, zIndex: 1000,
        background: 'rgba(10,14,26,0.85)', border: '1px solid #1f2d45',
        borderRadius: 8, padding: '8px 10px', minWidth: 170,
      }}>
        <div style={{ fontSize: 10, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 2 }}>
          Vessels in transit
        </div>
        <div style={{ fontSize: 15, fontWeight: 700, color: '#fbbf24' }}>
          {vesselEstimate != null ? vesselEstimate.toFixed(1) : '—'}
        </div>
        <div style={{ fontSize: 10, color: '#64748b', marginTop: 2 }}>
          Estimated, not tracked
        </div>
        {vesselNote && (
          <div style={{ fontSize: 9, color: '#475569', marginTop: 4, lineHeight: 1.3 }}>
            {vesselNote}
          </div>
        )}
      </div>

      {isReady ? (
        <MapContainer
          key={mapKey}
          center={[20, 60]}
          zoom={3}
          minZoom={2}
          maxZoom={6}
          style={{ height: '100%', width: '100%', minHeight: 340 }}
          attributionControl={false}
          zoomControl={false}
        >
          {/* Zoom controls — moved to bottom-right so they don't overlap the VESSELS IN TRANSIT stat card at top-left */}
          <ZoomControl position="bottomright" />
          <TileLayer
            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
            attribution='&copy; <a href="https://carto.com/">CARTO</a>'
          />

          {/* ─ Corridor polylines ─ */}
          {Object.entries(CORRIDOR_PATHS).map(([key, path]) => {
            const info   = lookup[key];
            const level  = info?.level || 'green';
            const score  = info?.score ?? 0;
            const color  = LEVEL_HEX[level];
            const label  = CORRIDOR_LABELS[key] || key;
            const center = CORRIDOR_CENTERS[key];
            const offset   = LABEL_OFFSET[key] || [-2, 3];
            // Place the label at center+offset (degrees), not on the dot itself.
            // This separates the text from the CircleMarker and from India's coastline.
            const labelPos = center ? [center[0] + offset[0], center[1] + offset[1]] : null;

            return (
              <Fragment key={key}>
                <Polyline
                  key={`${key}-line`}
                  positions={path}
                  pathOptions={{
                    color,
                    weight:    level === 'red' ? 4 : level === 'amber' ? 3 : 2,
                    opacity:   level === 'red' ? 0.95 : 0.75,
                    dashArray: level === 'green' ? '6 4' : undefined,
                  }}
                >
                  <Tooltip sticky>
                    <div style={{ fontFamily: 'Inter, sans-serif', fontSize: 12, minWidth: 180 }}>
                      <strong style={{ color }}>{label}</strong><br />
                      Risk score: <strong>{score.toFixed(1)}</strong> / 100<br />
                      Status: <span style={{ color, fontWeight: 700 }}>{LEVEL_LABEL[level]}</span><br />
                      {info?.articles_in_window != null && (
                        <span style={{ color: '#94a3b8', fontSize: 11 }}>
                          {info.articles_in_window} article{info.articles_in_window !== 1 ? 's' : ''} in 7-day window
                        </span>
                      )}
                      {info?.top_headlines?.[0] && (
                        <div style={{ marginTop: 5, maxWidth: 240, color: '#cbd5e1', fontSize: 11, borderTop: '1px solid #334155', paddingTop: 4 }}>
                          "{info.top_headlines[0].title.slice(0, 90)}…"
                        </div>
                      )}
                    </div>
                  </Tooltip>
                </Polyline>

                {/* Glow dot at corridor center */}
                {center && (
                  <CircleMarker
                    key={`${key}-dot`}
                    center={center}
                    radius={level === 'red' ? 7 : level === 'amber' ? 5 : 4}
                    pathOptions={{ color, fillColor: color, fillOpacity: 0.8, weight: 2 }}
                  >
                    <Tooltip direction="top" offset={[0, -8]}>
                      <strong>{label}</strong>: {score.toFixed(1)}
                    </Tooltip>
                  </CircleMarker>
                )}

                {/* Corridor name label — at labelPos (center+LABEL_OFFSET), not on the dot */}
                {labelPos && (
                  <Marker
                    key={`${key}-label`}
                    position={labelPos}
                    icon={makeLabelIcon(label, color)}
                    interactive={false}
                  />
                )}
              </Fragment>
            );
          })}

          {/* ─ India infrastructure markers (zoom-aware clustering via InfraLayer) ─ */}
          <InfraLayer sites={allInfra} showInfra={showInfra} />
        </MapContainer>
      ) : (
        <div style={{ height: '100%', minHeight: 340, borderRadius: 10, border: '1px solid #1f2d45', background: 'rgba(10,14,26,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#64748b' }}>
          Initializing map…
        </div>
      )}

      {/* Floating legend */}
      <MapLegend showInfra={showInfra} />

      {/* No-data overlay */}
      {noData && (
        <div style={{
          position: 'absolute', inset: 0, zIndex: 999,
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          background: 'rgba(10,14,26,0.65)', backdropFilter: 'blur(2px)',
          gap: 8, pointerEvents: 'none',
        }}>
          <div style={{ fontSize: 28 }}>🗺️</div>
          <div style={{ fontSize: 13, color: '#64748b', fontWeight: 600 }}>Awaiting pipeline data</div>
          <div style={{ fontSize: 11, color: '#334155' }}>
            Run <code style={{ color: '#7dd3fc' }}>live_macro_pipeline.py</code> then restart the API
          </div>
        </div>
      )}
    </div>
  );
}
