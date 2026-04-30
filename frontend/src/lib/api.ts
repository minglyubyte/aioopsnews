import type {
  AdminIncident,
  AdminIncidentQueueResponse,
  AdminIncidentUpdateRequest,
  Incident,
  IncidentFeedFilters,
  IncidentFeedResponse,
  IncidentFilters,
} from "../types/incident";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

async function getJson<T>(
  path: string,
  searchParams?: URLSearchParams,
  headers?: HeadersInit,
): Promise<T> {
  const suffix =
    searchParams && searchParams.size ? `?${searchParams.toString()}` : "";
  const response = await fetch(`${API_BASE_URL}${path}${suffix}`, {
    headers,
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }

  return (await response.json()) as T;
}

export function fetchIncidentFeed(
  filters?: IncidentFeedFilters,
): Promise<IncidentFeedResponse> {
  const searchParams = new URLSearchParams();

  if (filters?.category) {
    searchParams.set("category", filters.category);
  }
  if (filters?.company) {
    searchParams.set("company", filters.company);
  }
  if (filters?.claimant) {
    searchParams.set("claimant", filters.claimant);
  }
  if (filters?.severityMin) {
    searchParams.set("severity_min", String(filters.severityMin));
  }
  if (filters?.severityMax) {
    searchParams.set("severity_max", String(filters.severityMax));
  }
  if (filters?.page && filters.page > 1) {
    searchParams.set("page", String(filters.page));
  }
  if (filters?.pageSize) {
    searchParams.set("page_size", String(filters.pageSize));
  }

  return getJson<IncidentFeedResponse>("/incidents", searchParams);
}

export function fetchIncidentDetail(incidentId: string): Promise<Incident> {
  return getJson<Incident>(`/incidents/${incidentId}`);
}

export function fetchIncidentFilters(): Promise<IncidentFilters> {
  return getJson<IncidentFilters>("/filters");
}

export function fetchAdminIncidentQueue(
  adminToken: string,
): Promise<AdminIncidentQueueResponse> {
  return getJson<AdminIncidentQueueResponse>("/admin/incidents", undefined, {
    "X-Admin-Token": adminToken,
  });
}

export async function updateAdminIncident(
  adminToken: string,
  incidentId: string,
  payload: AdminIncidentUpdateRequest,
): Promise<AdminIncident> {
  const response = await fetch(
    `${API_BASE_URL}/admin/incidents/${incidentId}`,
    {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        "X-Admin-Token": adminToken,
      },
      body: JSON.stringify(payload),
    },
  );

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }

  return (await response.json()) as AdminIncident;
}
