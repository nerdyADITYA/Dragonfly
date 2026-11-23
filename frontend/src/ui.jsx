const TONE = {
  passed: 'bg-green-100 text-green-800', completed: 'bg-green-100 text-green-800', approved: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800', blocked: 'bg-orange-100 text-orange-800', timed_out: 'bg-orange-100 text-orange-800',
  running: 'bg-blue-100 text-blue-800', queued: 'bg-blue-100 text-blue-800',
  inconclusive: 'bg-purple-100 text-purple-800', rejected: 'bg-slate-200 text-slate-600',
}

export function Badge({ children }) {
  return (
    <span className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${TONE[children] || 'bg-slate-100 text-slate-700'}`}>
      {String(children).replace('_', ' ')}
    </span>
  )
}

export function Card({ title, actions, children }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      {(title || actions) && (
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-semibold">{title}</h2>
          <div className="flex gap-2">{actions}</div>
        </div>
      )}
      {children}
    </section>
  )
}

export function Button({ variant = 'primary', className = '', ...props }) {
  const styles = {
    primary: 'bg-indigo-600 text-white hover:bg-indigo-700',
    secondary: 'border border-slate-300 bg-white hover:bg-slate-50',
    danger: 'border border-red-300 bg-white text-red-700 hover:bg-red-50',
  }
  return <button className={`rounded px-3 py-1.5 text-sm font-medium disabled:opacity-50 ${styles[variant]} ${className}`} {...props} />
}

export const Empty = ({ children }) => <p className="py-4 text-sm text-slate-500">{children}</p>
export const ErrorBox = ({ error }) =>
  error ? <p role="alert" className="rounded bg-red-50 p-2 text-sm text-red-700">{error.message || String(error)}</p> : null
export const Loading = () => <p className="py-4 text-sm text-slate-500">Loading…</p>

export function Field({ label, hint, children }) {
  return (
    <label className="block text-sm">
      <span className="font-medium">{label}</span>
      {children}
      {hint && <span className="mt-0.5 block text-xs text-slate-500">{hint}</span>}
    </label>
  )
}

export const inputCls = 'mt-1 block w-full rounded border border-slate-300 px-2 py-1.5 text-sm'
export const fmt = (d) => (d ? new Date(d).toLocaleString() : '—')
