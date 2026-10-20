import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ClipboardList, ShoppingBasket, Clock, Scale, Plus, ArrowRight, Pencil } from 'lucide-react';
import { useStore } from '../../hooks/useStore';
import { remaining } from '../../data/mock';
import { PageHeader, StatCard, Field, EmptyState, Badge, ProduceCard, SectionHead, number, Modal } from '../../components/UI';

export function BuyerDashboard() {
  const { produce, requirements, transactions, loading, loadError } = useStore();
  const active = requirements.filter(requirement => ['OPEN', 'PARTIALLY_FILLED'].includes(requirement.status));
  const accepted = transactions.filter(item => item.transaction_type === 'PRIMARY_SALE').reduce((sum, item) => sum + Number(item.quantity_kg), 0);
  if (loading) return <section className="panel"><p className="muted">Loading sourcing data…</p></section>;
  if (loadError) return <section className="panel"><p role="alert">{loadError}</p></section>;
  return <><PageHeader title="A fresher way to source" description="Discover harvests matched to your active requirements."><Link to="/buyer/requirements" className="button"><Plus size={17}/>New requirement</Link></PageHeader>
    <div className="stats-grid"><StatCard label="Active requirements" value={active.length} icon={ClipboardList} note="Backend requirements"/><StatCard label="Available produce" value={produce.filter(p => remaining(p) > 0).length} icon={ShoppingBasket} note="Matched listings"/><StatCard label="Open requirements" value={active.length} icon={Clock} note="Awaiting fulfilment"/><StatCard label="Primary accepted quantity" value={number(accepted)} unit="kg" icon={Scale} note="Recorded transactions"/></div>
    <div className="info-banner"><Badge tone="green">PARTIAL QUANTITY FULFILMENT</Badge><p>Accept only the quantity you need. AgriRoute updates the farmer’s remaining inventory and your requirement balance.</p></div>
    <SectionHead title="Matched opportunities" to="/buyer/available-produce"/><div className="produce-grid three">{produce.filter(p => remaining(p) > 0).slice(0, 3).map(p => <ProduceCard key={p.id} p={p} action={<Link className="text-link" to="/buyer/available-produce">View matches<ArrowRight size={16}/></Link>}/>)}</div>
    {!produce.length && <div className="panel"><EmptyState title="No compatible produce yet" description="Your active requirements will be matched as farmers list compatible harvests."/></div>}
  </>;
}

export function Requirements() {
  const { requirements, addRequirement, updateRequirementCriteria, cancelRequirement } = useStore();
  const [form, setForm] = useState({ crop: '', quantity: '', grade: 'A', min: '', max: '', distance: '', pickup: '', location: '' });
  const [editing, setEditing] = useState(null);
  const [editForm, setEditForm] = useState(null);
  const [saving, setSaving] = useState(false);
  const [cancelling, setCancelling] = useState(null);
  const fields = [['crop', 'Crop', 'text'], ['quantity', 'Required quantity (kg)', 'number'], ['grade', 'Minimum quality', 'text'], ['min', 'Minimum price (₹/kg)', 'number'], ['max', 'Maximum price (₹/kg)', 'number'], ['distance', 'Maximum distance (km)', 'number'], ['pickup', 'Pickup date (optional)', 'date'], ['location', 'Location', 'text']];

  function beginEdit(requirement) {
    setEditing(requirement);
    setEditForm({ grade: requirement.grade, min: String(requirement.min), max: String(requirement.max), distance: requirement.distance == null ? '' : String(requirement.distance), pickup: requirement.pickup ?? '', location: requirement.location ?? '' });
  }

  async function saveEdit(event) {
    event.preventDefault();
    if (!editing || !editForm || Number(editForm.min) > Number(editForm.max)) return;
    setSaving(true);
    const saved = await updateRequirementCriteria(editing.id, {
      minimum_quality: editForm.grade.trim(), minimum_price_per_kg: Number(editForm.min), maximum_price_per_kg: Number(editForm.max),
      maximum_distance_km: editForm.distance === '' ? null : Number(editForm.distance), pickup_date: editForm.pickup || null,
      location_name: editForm.location.trim() || null,
    });
    setSaving(false);
    if (saved) { setEditing(null); setEditForm(null); }
  }

  return <><PageHeader title="Your sourcing requirements" description="Define what you need, without committing to the whole harvest."/><div className="detail-grid">
    <form className="panel form-section" onSubmit={event => { event.preventDefault(); if (Number(form.min) > Number(form.max)) return; addRequirement(form); }}><h2>Create a requirement</h2><div className="form-grid">{fields.map(([key, label, type]) => <Field key={key} label={label}><input required={!['pickup', 'location'].includes(key)} type={type} min={key === 'max' ? form.min : key === 'distance' ? '0' : '1'} step={type === 'number' ? '0.01' : undefined} value={form[key]} onChange={event => setForm({ ...form, [key]: event.target.value })}/></Field>)}</div><button className="button" type="submit"><Plus size={17}/>Save requirement</button></form>
    <section><SectionHead title="Saved requirements"/>{!requirements.length ? <div className="panel"><EmptyState title="Start with what you need" description="Your saved requirements will appear here."/></div> : requirements.map(requirement => { const active = ['OPEN', 'PARTIALLY_FILLED'].includes(requirement.status); return <div key={requirement.id} className="panel requirement-card"><Badge tone={active ? 'blue' : 'neutral'}>{requirement.status}</Badge><h3>{requirement.crop} · {requirement.remaining} kg remaining</h3><p>Grade {requirement.grade} · ₹{requirement.min}–{requirement.max}/kg · Within {requirement.distance ?? 'any'} km</p><p>{requirement.location || 'Location not specified'} · Pickup {requirement.pickup || 'flexible'}</p>{active && <div className="requirement-actions"><Link className="text-link" to="/buyer/available-produce">Browse matched produce<ArrowRight size={16}/></Link><button className="button secondary" type="button" onClick={() => beginEdit(requirement)}><Pencil size={15}/>Edit criteria</button><button className="button secondary" type="button" onClick={() => setCancelling(requirement)}>Cancel requirement</button></div>}</div>; })}</section>
  </div>
  {cancelling && <Modal title={`Cancel ${cancelling.crop} requirement?`} onClose={() => setCancelling(null)}><p>This stops future matching for the remaining {cancelling.remaining} kg. Existing allocations and transaction records remain unchanged.</p><div className="requirement-actions"><button className="button secondary" onClick={() => setCancelling(null)}>Keep requirement</button><button className="button" onClick={async () => { const done = await cancelRequirement(cancelling.id); if (done) setCancelling(null); }}>Confirm cancellation</button></div></Modal>}
  {editing && editForm && <Modal title={`Edit ${editing.crop} matching criteria`} onClose={() => !saving && setEditing(null)}><form className="form-section" onSubmit={saveEdit}><p className="muted">Crop and requested quantity stay fixed after creation. Update the criteria used for future matches.</p><div className="form-grid">{[['grade', 'Minimum quality', 'text'], ['min', 'Minimum price (₹/kg)', 'number'], ['max', 'Maximum price (₹/kg)', 'number'], ['distance', 'Maximum distance (km)', 'number'], ['pickup', 'Pickup date (optional)', 'date'], ['location', 'Location', 'text']].map(([key, label, type]) => <Field key={key} label={label}><input required={!['distance', 'pickup', 'location'].includes(key)} type={type} min={key === 'distance' ? '0' : '0'} step={type === 'number' ? '0.01' : undefined} value={editForm[key]} onChange={event => setEditForm({ ...editForm, [key]: event.target.value })}/></Field>)}</div>{Number(editForm.min) > Number(editForm.max) && <p role="alert">Maximum price must be at least the minimum price.</p>}<button className="button full" disabled={saving || Number(editForm.min) > Number(editForm.max)}>{saving ? 'Saving…' : 'Save criteria'}</button></form></Modal>}
  </>;
}
