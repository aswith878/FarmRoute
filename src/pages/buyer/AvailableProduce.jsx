import { useMemo, useState } from 'react';
import { ArrowRight, ShieldCheck } from 'lucide-react';
import { useStore } from '../../hooks/useStore';
import { remaining } from '../../data/mock';
import { PageHeader, Field, Badge, ProduceCard, Modal, EmptyState } from '../../components/UI';

export default function AvailableProduce() {
  const { produce, requirements, acceptPrimary, loading, loadError } = useStore();
  const open = requirements.filter(requirement => ['OPEN', 'PARTIALLY_FILLED'].includes(requirement.status));
  const [requirementId, setRequirementId] = useState('');
  const selectedRequirement = open.find(requirement => String(requirement.id) === String(requirementId)) ?? open[0];
  const [quantity, setQuantity] = useState('');
  const [crop, setCrop] = useState('All crops');
  const [selected, setSelected] = useState(null);
  const listings = useMemo(() => produce.filter(item => remaining(item) > 0
    && (!selectedRequirement || item.crop.toLowerCase() === selectedRequirement.crop.toLowerCase())
    && (crop === 'All crops' || item.crop === crop)), [produce, crop, selectedRequirement]);
  const amount = Number(quantity || selectedRequirement?.remaining || 0);
  const valid = item => selectedRequirement && Number.isFinite(amount) && amount > 0
    && amount <= remaining(item) && amount <= selectedRequirement.remaining;

  return <><PageHeader title="Available produce" description="Browse harvests matched to your active sourcing requirements."/>
    {loading && <section className="panel"><p className="muted">Loading matched produce…</p></section>}
    {loadError && <section className="panel"><p role="alert">{loadError}</p></section>}
    {!loading && !loadError && <>
      <section className="panel sourcing-toolbar">
        <Field label="Your active requirement"><select aria-label="Your active requirement" value={selectedRequirement?.id ?? ''} onChange={event => { setRequirementId(event.target.value); setQuantity(''); }}>
          {!open.length && <option value="">Create a requirement first</option>}
          {open.map(item => <option key={item.id} value={item.id}>{item.crop} · {item.remaining} kg remaining · Grade {item.grade}</option>)}
        </select></Field>
        <Field label="Required quantity (kg)" type="number"><input type="number" min="0.001" step="0.001" max={Math.min(selectedRequirement?.remaining ?? 0, selected ? remaining(selected) : Infinity)} value={quantity || selectedRequirement?.remaining || ''} onChange={event => setQuantity(event.target.value)} disabled={!selectedRequirement}/></Field>
        <Field label="Crop"><select value={crop} onChange={event => setCrop(event.target.value)}>{['All crops', ...new Set(produce.map(item => item.crop))].map(name => <option key={name}>{name}</option>)}</select></Field>
        <div><small>Buyer</small><strong>{useStore().user?.name ?? 'Your organization'}</strong></div>
      </section>
      {!open.length && <div className="panel"><EmptyState title="Create a sourcing requirement" description="Matched harvests appear here after you save a requirement."/></div>}
      {!!open.length && <><div className="info-banner"><ShieldCheck size={19}/><p>These listings are returned by AgriRoute’s compatibility matching. Review the quantity and offer before accepting.</p><Badge tone="blue">LIVE REQUIREMENTS</Badge></div>
        <div className="produce-grid three">{listings.map(item => <div key={item.id} className="sourcing-card"><div className="sourcing-ranking"><span>COMPATIBLE HARVEST</span><strong>AgriRoute match</strong></div><ProduceCard p={item} action={<Badge tone="blue">{item.location}</Badge>}/><div className="sourcing-action"><span>{item.location}</span><p>Grade {item.grade} · Listed at ₹{item.price}/kg</p><p>Requirement balance: {selectedRequirement?.remaining ?? 0} kg</p><button className="button full" disabled={!valid(item)} onClick={() => setSelected(item)}>Accept {amount || 0} kg<ArrowRight size={16}/></button>{!valid(item) && <small>Enter a positive quantity within both available inventory and your remaining requirement.</small>}</div></div>)}</div>
        {!listings.length && <EmptyState title="No compatible harvests found" description="Try another crop or update your active requirement."/>}</>}
      {selected && selectedRequirement && <Modal title="Confirm primary allocation" onClose={() => setSelected(null)}><p>{selected.crop} · {selected.id} → {selectedRequirement.crop} requirement</p><div className="info-list"><div><span>Available quantity</span><strong>{remaining(selected)} kg</strong></div><div><span>Requirement balance</span><strong>{selectedRequirement.remaining} kg</strong></div><div><span>Quantity being accepted</span><strong>{amount} kg</strong></div><div className="highlight"><span>Farmer inventory after transaction</span><strong>{remaining(selected)-amount} kg</strong></div></div><p className="modal-explain">AgriRoute will record the sale and update both produce inventory and your requirement balance.</p><button className="button full" disabled={!valid(selected)} onClick={async () => { const ok = await acceptPrimary(selected.id, amount, selectedRequirement.id); if (ok) setSelected(null); }}>Accept {amount} kg</button></Modal>}
    </>}
  </>;
}
