import type {
  AdminIncident,
  AdminIncidentQueueResponse,
  AdminIncidentUpdateRequest,
  IncidentFeedResponse,
  IncidentFilters,
} from "../types/incident";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`);

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }

  return (await response.json()) as T;
}

export function fetchIncidentFeed(): Promise<IncidentFeedResponse> {
  return getJson<IncidentFeedResponse>("/incidents");
}

export function fetchIncidentFilters(): Promise<IncidentFilters> {
  return getJson<IncidentFilters>("/filters");
}

export function fetchAdminIncidentQueue(): Promise<AdminIncidentQueueResponse> {
  return getJson<AdminIncidentQueueResponse>("/admin/incidents");
}

export async function updateAdminIncident(
  incidentId: string,
  payload: AdminIncidentUpdateRequest,
): Promise<AdminIncident> {
  const response = await fetch(
    `${API_BASE_URL}/admin/incidents/${incidentId}`,
    {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    },
  );

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }

  return (await response.json()) as AdminIncident;
}
