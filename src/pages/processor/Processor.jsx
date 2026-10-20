import { useEffect, useState } from 'react';
import { Factory, Clock, Check, Scale, ShieldCheck, Pencil } from 'lucide-react';
import { useStore } from '../../hooks/useStore';
import { agriRouteApi } from '../../api/agriRoute';
import { PageHeader, StatCard, Badge, Modal, EmptyState, Field } from '../../components/UI';

export default function Processor({ dashboard = false }) {
  const { user, routingCases, processorRequirements, alternativeAllocations, addProcessorRequirement, updateRequirementCriteria, cancelRequirement, loading, loadError, refresh, notify } = useStore();
  const [offers, setOffers] = useState([]);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ condition: '', utilization: '', notes: '' });
  const [editingRequirement, setEditingRequirement] = useState(null);
  const [requirementEdit, setRequirementEdit] = useState(null);
  const [savingRequirement, setSavingRequirement] = useState(false);
  const [cancellingRequirement, setCancellingRequirement] = useState(null);
  const [requirement, setRequirement] = useState({ crop: '', quantity: '', grade: 'B', conditions: 'NO VISIBLE DAMAGE, MINOR SURFACE DAMAGE', utilization: '', min: '0', max: '100', distance: '', pickup: '', location: '' });
  const acceptedQuantity = alternativeAllocations.reduce((total, allocation) => total + Number(allocation.quantity_kg), 0);

  useEffect(() => {
    let current = true;
    Promise.all(routingCases.map(async routingCase => {
      const result = await agriRouteApi.processorMatches(routingCase.id);
      return result.matches.map(match => ({ ...match, routingCase }));
    })).then(groups => { if (current) { setOffers(groups.flat()); setError(''); } })
      .catch(reason => { if (current) setError(reason.message); });
    return () => { current = false; };
  }, [routingCases]);

  async function confirm() {
    if (!selected || !form.condition.trim() || !form.utilization.trim() || !form.notes.trim()) return;
    setBusy(true);
    try {
      await agriRouteApi.suitability(selected.routingCase.id, {
        processor_requirement_id: selected.processor_requirement_id,
        intended_utilization: form.utilization,
        confirmed_condition: form.condition,
        suitable: true,
        assessed_by: user.name,
        assessment_notes: form.notes,
      });
      await agriRouteApi.acceptAlternative(selected.routingCase.id, {
        processor_requirement_id: selected.processor_requirement_id,
        accepted_quantity_kg: Number(selected.compatible_quantity_kg),
      }, crypto.randomUUID());
      await refresh(); setSelected(null); setForm({ condition: '', utilization: '', notes: '' });
      notify('Suitability recorded and alternative allocation accepted.');
    } catch (reason) { notify(reason.message || 'The processor allocation could not be completed.'); }
    finally { setBusy(false); }
  }

  function editRequirement(item) {
    setEditingRequirement(item);
    setRequirementEdit({
      grade: item.minimum_acceptable_quality,
      conditions: item.acceptable_produce_conditions.join(', '),
      utilization: item.intended_utilization,
      min: String(item.minimum_price_per_kg),
      max: String(item.maximum_price_per_kg),
      distance: item.maximum_distance_km == null ? '' : String(item.maximum_distance_km),
      pickup: item.pickup_date ?? '',
      location: item.location_name ?? '',
    });
  }

  async function saveRequirement(event) {
    event.preventDefault();
    if (!editingRequirement || !requirementEdit || Number(requirementEdit.min) > Number(requirementEdit.max)) return;
    setSavingRequirement(true);
    const saved = await updateRequirementCriteria(editingRequirement.id, {
      minimum_acceptable_quality: requirementEdit.grade.trim(),
      acceptable_produce_conditions: requirementEdit.conditions.split(',').map(item => item.trim()).filter(Boolean),
      intended_utilization: requirementEdit.utilization.trim(),
      minimum_price_per_kg: Number(requirementEdit.min), maximum_price_per_kg: Number(requirementEdit.max),
      maximum_distance_km: requirementEdit.distance === '' ? null : Number(requirementEdit.distance),
      pickup_date: requirementEdit.pickup || null, location_name: requirementEdit.location.trim() || null,
    }, true);
    setSavingRequirement(false);
    if (saved) { setEditingRequirement(null); setRequirementEdit(null); }
  }

  if (loading) return <section className="panel"><p className="muted">Loading processor opportunities…</p></section>;
  if (loadError) return <section className="panel"><p role="alert">{loadError}</p></section>;
  return <><PageHeader title="Alternative Utilization Opportunities" description="Review eligible produce against your processor requirements and record suitability before accepting."/>
    <form className="panel form-section" onSubmit={event => { event.preventDefault(); addProcessorRequirement(requirement); }}><h2>Create a processing requirement</h2><p className="muted">Requirements control which eligible produce is matched to your facility.</p><div className="form-grid">{[['crop','Crop'],['quantity','Required quantity (kg)'],['grade','Minimum quality'],['conditions','Accepted conditions (comma-separated)'],['utilization','Intended utilization'],['min','Minimum price (₹/kg)'],['max','Maximum price (₹/kg)'],['distance','Maximum distance (km)'],['pickup','Pickup date'],['location','Location']].map(([key,label]) => <Field key={key} label={label}><input required={!['distance','pickup','location'].includes(key)} type={['quantity','min','max','distance'].includes(key)?'number':key==='pickup'?'date':'text'} min={key==='distance'?'0':key==='min'?'0':'1'} step="0.01" value={requirement[key]} onChange={event => setRequirement({...requirement,[key]:event.target.value})}/></Field>)}</div><button className="button" type="submit">Save processor requirement</button><p className="muted">{processorRequirements.length} requirements loaded from AgriRoute.</p></form>
    {!!processorRequirements.length && <section className="panel requirement-management"><h2>Your processing requirements</h2><p className="muted">Adjust match criteria as your facility capacity and acceptance conditions change.</p>{processorRequirements.map(item => <div className="requirement-manage-row" key={item.id}><div><strong>{item.crop_name} · {Number(item.remaining_requirement_kg)} kg remaining</strong><small>{item.status} · {item.intended_utilization} · Grade {item.minimum_acceptable_quality}</small></div>{["OPEN", "PARTIALLY_FILLED"].includes(item.status) && <><button className="button secondary" type="button" onClick={() => editRequirement(item)}><Pencil size={15}/>Edit criteria</button><button className="button secondary" type="button" onClick={() => setCancellingRequirement(item)}>Cancel requirement</button></>}</div>)}</section>}
    {dashboard && <div className="stats-grid"><StatCard label="Matched opportunities" value={offers.length} icon={Factory} note="From active requirements"/><StatCard label="High urgency cases" value={routingCases.length} icon={Clock} note="Available for review" tone="amber"/><StatCard label="Processor requirements" value={processorRequirements.filter(item => ['OPEN', 'PARTIALLY_FILLED'].includes(item.status)).length} icon={Check} note="Active capacity"/><StatCard label="Accepted allocations" value={alternativeAllocations.length} icon={Scale} note={`${acceptedQuantity.toLocaleString()} kg accepted`}/></div>}
    <section className="panel requirement-management"><h2>Accepted allocations</h2><p className="muted">Backend records of produce accepted after suitability assessment.</p>{!alternativeAllocations.length ? <EmptyState title="No allocations accepted yet" description="Completed processor acceptances will be recorded here."/> : <div className="allocation-history">{[...alternativeAllocations].sort((a, b) => new Date(b.created_at) - new Date(a.created_at)).map(allocation => <div className="requirement-manage-row" key={allocation.id}><div><strong>{Number(allocation.quantity_kg).toLocaleString()} kg · {allocation.intended_utilization.replaceAll('_', ' ')}</strong><small>{allocation.status} · Allocation #{allocation.id} · Routing case #{allocation.routing_case_id} · Batch #{allocation.produce_batch_id}</small></div><Badge tone="green">{allocation.price_per_kg == null ? 'Price not recorded' : `₹${Number(allocation.price_per_kg)}/kg`}</Badge></div>)}</div>}</section>
    <div className="info-banner"><ShieldCheck size={20}/><p>Record the observed condition and intended use. Acceptance requires an explicit suitability assessment.</p><Badge tone="purple">LIVE CASES</Badge></div>
    {error && <section className="panel" role="alert">{error}</section>}
    {!error && !offers.length && <EmptyState title="No matching alternative opportunities" description="Eligible cases appear when your requirements match a farmer’s routing case."/>}
    <div className="produce-grid three">{offers.map(offer => <article className="panel opportunity" key={`${offer.routingCase.id}-${offer.processor_requirement_id}`}><div className="opportunity-top"><span><Factory size={26}/></span><Badge tone="amber">{offer.routingCase.risk_level_at_creation} urgency</Badge></div><h2>{offer.intended_utilization}</h2><span className="muted mono">Routing case #{offer.routingCase.id}</span><h3 className="opportunity-quantity">{Number(offer.compatible_quantity_kg)} <small>kg compatible</small></h3><div className="tags"><Badge tone="neutral">Requirement #{offer.processor_requirement_id}</Badge><Badge tone="green">{offer.match_score}% match</Badge></div><p>{offer.suitability_explanation}</p>{offer.warnings.map(warning => <small className="muted" key={warning}>{warning}</small>)}<button className="button full" onClick={() => { setSelected(offer); setForm({ condition: '', utilization: offer.intended_utilization, notes: '' }); }}>Assess and accept</button></article>)}</div>
    {cancellingRequirement && <Modal title={`Cancel ${cancellingRequirement.crop_name} requirement?`} onClose={() => setCancellingRequirement(null)}><p>This stops future matching for the remaining {Number(cancellingRequirement.remaining_requirement_kg)} kg. Existing allocations remain preserved.</p><div className="requirement-actions"><button className="button secondary" onClick={() => setCancellingRequirement(null)}>Keep requirement</button><button className="button" onClick={async () => { const done = await cancelRequirement(cancellingRequirement.id, true); if (done) setCancellingRequirement(null); }}>Confirm cancellation</button></div></Modal>}
    {selected && <Modal title="Record suitability and accept" onClose={() => !busy && setSelected(null)}><p>Routing case #{selected.routingCase.id} · {Number(selected.compatible_quantity_kg)} kg</p><Field label="Confirmed produce condition"><input required value={form.condition} onChange={event => setForm({ ...form, condition: event.target.value })} placeholder="Record your physical inspection"/></Field><Field label="Intended utilization"><input required value={form.utilization} onChange={event => setForm({ ...form, utilization: event.target.value })}/></Field><Field label="Assessment notes"><textarea required rows="3" value={form.notes} onChange={event => setForm({ ...form, notes: event.target.value })}/></Field><p className="modal-explain">The API will record your suitability assessment and accept the compatible quantity as one processor allocation.</p><button className="button full" disabled={busy || !form.condition.trim() || !form.notes.trim()} onClick={confirm}>{busy ? 'Saving assessment…' : 'Record assessment and accept'}</button></Modal>}
    {editingRequirement && requirementEdit && <Modal title={`Edit ${editingRequirement.crop_name} requirement`} onClose={() => !savingRequirement && setEditingRequirement(null)}><form className="form-section" onSubmit={saveRequirement}><p className="muted">Crop and required quantity stay fixed. Changes apply to future matches.</p><div className="form-grid">{[['grade','Minimum quality'],['conditions','Accepted conditions (comma-separated)'],['utilization','Intended utilization'],['min','Minimum price (₹/kg)'],['max','Maximum price (₹/kg)'],['distance','Maximum distance (km)'],['pickup','Pickup date'],['location','Location']].map(([key,label]) => <Field key={key} label={label}><input required={!['distance','pickup','location'].includes(key)} type={['min','max','distance'].includes(key)?'number':key==='pickup'?'date':'text'} min={key==='distance'?'0':key==='min'?'0':'1'} step="0.01" value={requirementEdit[key]} onChange={event => setRequirementEdit({...requirementEdit,[key]:event.target.value})}/></Field>)}</div>{Number(requirementEdit.min)>Number(requirementEdit.max)&&<p role="alert">Maximum price must be at least the minimum price.</p>}<button className="button full" disabled={savingRequirement||Number(requirementEdit.min)>Number(requirementEdit.max)}>{savingRequirement?'Saving…':'Save criteria'}</button></form></Modal>}
  </>;
}
