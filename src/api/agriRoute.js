import { apiRequest } from './client';

const json = (path, method = 'GET', body, options = {}) => apiRequest(path, {
  method, body, ...options,
});

export const agriRouteApi = Object.freeze({
  currentUser: () => json('/auth/me'),
  users: (query = '') => json(`/users${query}`),
  updateUser: (id, payload) => json(`/users/${id}`, 'PUT', payload),
  produce: (query = '') => json(`/produce${query}`),
  createProduce: payload => json('/produce', 'POST', payload),
  uploadProduceImage: (id, file) => {
    const form = new FormData();
    form.append('image', file);
    return json(`/produce/${id}/image`, 'POST', form);
  },
  updateProduce: (id, payload) => json(`/produce/${id}`, 'PUT', payload),
  primaryMatches: id => json(`/matches/produce/${id}`),
  requirements: (query = '') => json(`/buyer-requirements${query}`),
  createRequirement: payload => json('/buyer-requirements', 'POST', payload),
  updateRequirement: (id, payload) => json(`/buyer-requirements/${id}`, 'PUT', payload),
  cancelRequirement: id => json(`/buyer-requirements/${id}/cancel`, 'POST'),
  processorRequirements: (query = '') => json(`/processor-requirements${query}`),
  createProcessorRequirement: payload => json('/processor-requirements', 'POST', payload),
  updateProcessorRequirement: (id, payload) => json(`/processor-requirements/${id}`, 'PUT', payload),
  cancelProcessorRequirement: id => json(`/processor-requirements/${id}/cancel`, 'POST'),
  transactions: (query = '') => json(`/transactions${query}`),
  acceptPrimary: payload => json('/transactions/accept', 'POST', payload),
  timeline: id => json(`/produce/${id}/timeline`),
  routingReadiness: id => json(`/produce/${id}/routing-readiness`),
  matchingAttempt: id => json(`/produce/${id}/matching-attempts`, 'POST'),
  createRoutingCase: id => json(`/produce/${id}/rerouting`, 'POST'),
  routingCases: () => json('/routing-cases'),
  processorMatches: id => json(`/routing-cases/${id}/processor-matches`),
  suitability: (id, payload) => json(`/routing-cases/${id}/suitability`, 'POST', payload),
  acceptAlternative: (id, payload, key) => json(`/routing-cases/${id}/accept`, 'POST', payload, {
    headers: { 'Idempotency-Key': key },
  }),
  alternativeAllocations: () => json('/alternative-allocations'),
});

const icons = { tomato: '🍅', okra: '🌿', banana: '🍌', mango: '🥭', apple: '🍎', potato: '🥔' };
const words = value => String(value ?? '').toLowerCase().replaceAll('_', ' ');

export function toProduceView(batch, timeline = null, readiness = null) {
  const quantity = Number(batch.initial_quantity_kg);
  const sold = Number(batch.sold_quantity_kg);
  const rerouted = Number(batch.rerouted_quantity_kg);
  const history = (timeline?.events ?? []).map(event => ({
    title: words(event.event_type).replace(/\b\w/g, letter => letter.toUpperCase()),
    detail: event.description,
    time: new Date(event.timestamp).toLocaleString(),
  }));
  return {
    id: batch.batch_code,
    apiId: batch.id,
    crop: batch.crop_name,
    icon: icons[batch.crop_name.toLowerCase()] ?? '🌱',
    quantity,
    sold,
    rerouted,
    price: Number(batch.expected_price_per_kg),
    grade: batch.quality_grade,
    risk: words(batch.risk_level).replace(/\b\w/g, letter => letter.toUpperCase()),
    location: batch.location_name ?? 'Location not provided',
    age: `${Math.max(0, Math.floor((Date.now() - new Date(batch.harvest_date).getTime()) / 86400000))} days`,
    storage: batch.storage_type ?? 'Not specified',
    eligible: Boolean(readiness?.rerouting_candidate) || batch.status === 'REROUTING',
    category: batch.category,
    harvest: batch.harvest_date,
    until: batch.available_until,
    condition: batch.visible_condition,
    defects: batch.cosmetic_defects,
    notes: batch.notes,
    imageUrl: batch.image_url,
    history,
    salesValue: sold * Number(batch.expected_price_per_kg),
    recoveryValue: 0,
    status: batch.status,
  };
}

export function toRequirementView(requirement) {
  return {
    id: requirement.id,
    crop: requirement.crop_name,
    quantity: Number(requirement.required_quantity_kg),
    remaining: Number(requirement.remaining_requirement_kg),
    grade: requirement.minimum_quality,
    min: Number(requirement.minimum_price_per_kg),
    max: Number(requirement.maximum_price_per_kg),
    distance: requirement.maximum_distance_km == null ? null : Number(requirement.maximum_distance_km),
    pickup: requirement.pickup_date,
    location: requirement.location_name,
    status: requirement.status,
  };
}
