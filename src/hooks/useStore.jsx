import { useCallback, useContext, useEffect, useState } from 'react';
import { StoreContext as Store } from './StoreContext';
import { useAuth } from '../auth/AuthContext';
import { agriRouteApi, toProduceView, toRequirementView } from '../api/agriRoute';

const messages = {
  FARMER: 'Could not load your produce from AgriRoute.',
  BUYER: 'Could not load sourcing opportunities from AgriRoute.',
  PROCESSOR: 'Could not load processing opportunities from AgriRoute.',
  ADMIN: 'Could not load AgriRoute network data.',
};

export function StoreProvider({ children }) {
  const { user } = useAuth();
  const role = user?.role?.toLowerCase() ?? null;
  const [produce, setProduce] = useState([]);
  const [requirements, setRequirements] = useState([]);
  const [processorRequirements, setProcessorRequirements] = useState([]);
  const [transactions, setTransactions] = useState([]);
  const [alternativeAllocations, setAlternativeAllocations] = useState([]);
  const [routingCases, setRoutingCases] = useState([]);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [toast, setToast] = useState('');
  const notify = useCallback(message => setToast(message), []);

  const refresh = useCallback(async () => {
    if (!user) {
      setProduce([]); setRequirements([]); setProcessorRequirements([]); setTransactions([]); setAlternativeAllocations([]); setRoutingCases([]); setUsers([]);
      setLoading(false); setLoadError('');
      return;
    }
    setLoading(true); setLoadError('');
    try {
      const roleName = user.role;
      const [batches, reqs, processorReqs, sales, allocations, cases, people] = await Promise.all([
        ['FARMER', 'BUYER', 'ADMIN'].includes(roleName) ? agriRouteApi.produce() : Promise.resolve([]),
        roleName === 'BUYER' ? agriRouteApi.requirements() : Promise.resolve([]),
        roleName === 'PROCESSOR' ? agriRouteApi.processorRequirements() : Promise.resolve([]),
        ['FARMER', 'BUYER', 'ADMIN'].includes(roleName) ? agriRouteApi.transactions() : Promise.resolve([]),
        ['FARMER', 'PROCESSOR', 'ADMIN'].includes(roleName) ? agriRouteApi.alternativeAllocations() : Promise.resolve([]),
        ['FARMER', 'PROCESSOR'].includes(roleName) ? agriRouteApi.routingCases() : Promise.resolve([]),
        roleName === 'ADMIN' ? agriRouteApi.users() : Promise.resolve([]),
      ]);
      const histories = await Promise.all(batches.map(batch => agriRouteApi.timeline(batch.id).catch(() => null)));
      const readiness = ['FARMER', 'ADMIN'].includes(roleName)
        ? await Promise.all(batches.map(batch => agriRouteApi.routingReadiness(batch.id).catch(() => null)))
        : batches.map(() => null);
      setProduce(batches.map((batch, index) => toProduceView(batch, histories[index], readiness[index])));
      setRequirements(reqs.map(toRequirementView)); setProcessorRequirements(processorReqs);
      setTransactions(sales); setAlternativeAllocations(allocations); setRoutingCases(cases); setUsers(people);
    } catch (error) {
      setLoadError(error.message || messages[user.role] || 'Could not load AgriRoute data.');
    } finally { setLoading(false); }
  }, [user]);

  useEffect(() => { refresh(); }, [refresh]);

  async function addProduce(form, imageFile = null) {
    try {
      let batch = await agriRouteApi.createProduce({
        farmer_id: user.id, crop_name: form.crop.trim(), category: form.category,
        initial_quantity_kg: Number(form.quantity), expected_price_per_kg: Number(form.price),
        harvest_date: form.harvest, available_until: form.until || null,
        quality_grade: form.grade, risk_level: form.grade === 'B' ? 'MEDIUM' : 'LOW',
        storage_type: form.storage, visible_condition: form.condition,
        cosmetic_defects: form.defects, notes: form.notes || null,
        image_url: null, location_name: form.location,
      });
      if (imageFile) {
        try {
          batch = await agriRouteApi.uploadProduceImage(batch.id, imageFile);
        } catch (error) {
          await refresh();
          notify(`${batch.batch_code} was listed, but its photo could not be saved. ${error.message}`);
          return batch;
        }
      }
      await refresh();
      notify(imageFile ? `${batch.batch_code} was listed with its photo. Primary matching is active.`
        : `${batch.batch_code} was listed. Primary matching is active.`);
      return batch;
    } catch (error) { notify(error.message || 'Produce could not be submitted.'); return null; }
  }

  async function addRequirement(form) {
    try {
      await agriRouteApi.createRequirement({
        buyer_id: user.id, crop_name: form.crop.trim(), required_quantity_kg: Number(form.quantity),
        minimum_quality: form.grade.trim().split(/[ /]/)[0], minimum_price_per_kg: Number(form.min),
        maximum_price_per_kg: Number(form.max), maximum_distance_km: form.distance ? Number(form.distance) : null,
        pickup_date: form.pickup || null, location_name: form.location || null,
      });
      await refresh(); notify('Requirement saved. Browse compatible produce.');
    } catch (error) { notify(error.message || 'Requirement could not be saved.'); }
  }

  async function addProcessorRequirement(form) {
    try {
      await agriRouteApi.createProcessorRequirement({
        processor_id: user.id, crop_name: form.crop.trim(), required_quantity_kg: Number(form.quantity),
        minimum_acceptable_quality: form.grade.trim().toUpperCase(),
        acceptable_produce_conditions: form.conditions.split(',').map(item => item.trim().toUpperCase()).filter(Boolean),
        intended_utilization: form.utilization.trim(), minimum_price_per_kg: Number(form.min),
        maximum_price_per_kg: Number(form.max), maximum_distance_km: form.distance ? Number(form.distance) : null,
        pickup_date: form.pickup || null, location_name: form.location || null,
      });
      await refresh(); notify('Processor requirement saved and matching is active.');
    } catch (error) { notify(error.message || 'Processor requirement could not be saved.'); }
  }

  async function updateRequirementCriteria(id, payload, processor = false) {
    try {
      const updated = processor
        ? await agriRouteApi.updateProcessorRequirement(id, payload)
        : await agriRouteApi.updateRequirement(id, payload);
      if (processor) setProcessorRequirements(current => current.map(item => item.id === updated.id ? updated : item));
      else setRequirements(current => current.map(item => item.id === updated.id ? toRequirementView(updated) : item));
      notify('Requirement matching criteria updated.');
      return true;
    } catch (error) {
      notify(error.message || 'Requirement could not be updated.');
      return false;
    }
  }

  async function cancelRequirement(id, processor = false) {
    try {
      const cancelled = processor
        ? await agriRouteApi.cancelProcessorRequirement(id)
        : await agriRouteApi.cancelRequirement(id);
      if (processor) setProcessorRequirements(current => current.map(item => item.id === cancelled.id ? cancelled : item));
      else setRequirements(current => current.map(item => item.id === cancelled.id ? toRequirementView(cancelled) : item));
      notify('Requirement cancelled. Existing allocations and records are preserved.');
      return true;
    } catch (error) {
      notify(error.message || 'Requirement could not be cancelled.');
      return false;
    }
  }

  async function accept(batchCode, amount, buyerName, alternative = false, requirementId = null) {
    if (alternative) { notify('Alternative allocations require a routing case and recorded suitability assessment.'); return false; }
    const batch = produce.find(row => row.id === batchCode);
    if (!batch) { notify('This produce batch is no longer available. Refresh and try again.'); return false; }
    try {
      const matchData = await agriRouteApi.primaryMatches(batch.apiId);
      const match = matchData.matches.find(row => requirementId != null
        ? row.buyer_requirement_id === Number(requirementId) : row.buyer_name === buyerName);
      if (!match) { notify('No current compatible requirement matches this buyer.'); return false; }
      await agriRouteApi.acceptPrimary({
        produce_batch_id: batch.apiId, buyer_requirement_id: match.buyer_requirement_id,
        quantity_kg: Number(amount), price_per_kg: Number(batch.price),
      });
      await refresh(); notify(`${amount} kg accepted. Inventory was updated by AgriRoute.`); return true;
    } catch (error) { notify(error.message || 'The allocation could not be accepted.'); return false; }
  }

  async function acceptPrimary(batchCode, amount, requirementId) {
    const batch = produce.find(row => row.id === batchCode);
    if (!batch) { notify('This produce batch is no longer available.'); return false; }
    try {
      await agriRouteApi.acceptPrimary({ produce_batch_id: batch.apiId,
        buyer_requirement_id: Number(requirementId), quantity_kg: Number(amount), price_per_kg: Number(batch.price) });
      await refresh(); notify(`${amount} kg accepted. Inventory was updated by AgriRoute.`); return true;
    } catch (error) { notify(error.message || 'The allocation could not be accepted.'); return false; }
  }

  async function advance(batchCode) {
    const batch = produce.find(row => row.id === batchCode);
    if (!batch) return;
    try {
      await agriRouteApi.matchingAttempt(batch.apiId);
      const readiness = await agriRouteApi.routingReadiness(batch.apiId);
      if (readiness.rerouting_candidate) await agriRouteApi.createRoutingCase(batch.apiId);
      await refresh();
      notify(readiness.rerouting_candidate ? 'Routing review is available based on recorded matching history.' : 'Matching attempt recorded. Primary matching continues.');
    } catch (error) { notify(error.message || 'Matching attempt could not be recorded.'); }
  }

  async function setAccountActive(account, isActive) {
    try {
      const updated = await agriRouteApi.updateUser(account.id, { is_active: isActive });
      setUsers(current => current.map(person => person.id === updated.id ? updated : person));
      notify(`${updated.name}'s account is now ${updated.is_active ? 'active' : 'inactive'}.`);
      return true;
    } catch (error) {
      notify(error.message || 'Account access could not be updated.');
      return false;
    }
  }

  return <Store.Provider value={{ user, produce, role, requirements, processorRequirements, transactions, alternativeAllocations, routingCases, users, loading, loadError,
    refresh, addRequirement, addProcessorRequirement, notify, toast, setToast, accept, acceptPrimary, advance, addProduce,
    setAccountActive, updateRequirementCriteria, cancelRequirement,
    reset: () => notify('Sample inventory reset is available in the demo build only.') }}>
    {children}
  </Store.Provider>;
}

export const useStore = () => useContext(Store);
