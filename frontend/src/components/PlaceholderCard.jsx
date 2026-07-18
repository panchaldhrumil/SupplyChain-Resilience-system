// PlaceholderCard — rich placeholder for teammate-owned PS2 modules
// Shows the defined input/output contract so judges can see the interface
// even before the module is implemented.
export default function PlaceholderCard({ title, description, icon = '🔧', inputs, outputs, owner }) {
  return (
    <div style={{
      background: 'rgba(17,24,39,0.6)',
      border: '1px dashed #1f2d45',
      borderRadius: 12,
      padding: '1.25rem',
      display: 'flex',
      flexDirection: 'column',
      gap: 12,
      minHeight: 180,
    }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
        <span style={{ fontSize: 24, filter: 'grayscale(0.4)', opacity: 0.7, flexShrink: 0 }}>{icon}</span>
        <div>
          <div style={{ fontSize: 13, fontWeight: 700, color: '#64748b', letterSpacing: '0.03em' }}>{title}</div>
          {description && (
            <div style={{ fontSize: 11, color: '#334155', marginTop: 3, lineHeight: 1.5 }}>{description}</div>
          )}
        </div>
        <span style={{
          marginLeft: 'auto', flexShrink: 0,
          fontSize: 9, fontWeight: 700, padding: '2px 8px', borderRadius: 999,
          background: 'rgba(71,85,105,0.15)', color: '#475569',
          border: '1px solid #1f2d45', letterSpacing: '0.08em', textTransform: 'uppercase',
        }}>
          {owner || 'Coming Soon'}
        </span>
      </div>

      {/* Module contract */}
      {(inputs || outputs) && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
          {inputs && (
            <div style={{
              padding: '8px 10px', borderRadius: 6,
              background: 'rgba(59,130,246,0.05)', border: '1px solid rgba(59,130,246,0.15)',
            }}>
              <div style={{ fontSize: 9, fontWeight: 700, color: '#3b82f6', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 6 }}>
                Expected Inputs
              </div>
              {inputs.map((inp, i) => (
                <div key={i} style={{ fontSize: 11, color: '#475569', marginBottom: 3, display: 'flex', gap: 5 }}>
                  <span style={{ color: '#1d4ed8' }}>›</span>
                  <span>{inp}</span>
                </div>
              ))}
            </div>
          )}
          {outputs && (
            <div style={{
              padding: '8px 10px', borderRadius: 6,
              background: 'rgba(34,197,94,0.05)', border: '1px solid rgba(34,197,94,0.15)',
            }}>
              <div style={{ fontSize: 9, fontWeight: 700, color: '#22c55e', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 6 }}>
                Expected Outputs
              </div>
              {outputs.map((out, i) => (
                <div key={i} style={{ fontSize: 11, color: '#475569', marginBottom: 3, display: 'flex', gap: 5 }}>
                  <span style={{ color: '#15803d' }}>›</span>
                  <span>{out}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
