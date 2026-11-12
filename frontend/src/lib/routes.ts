/** Page URLs. Studies and patients use query strings so the app exports as a static site. */
export const routes = {
  worklist: "/",
  patients: "/patients/",
  model: "/model/",
  study: (id: string) => `/case/?id=${encodeURIComponent(id)}`,
  patient: (id: string) => `/patient/?id=${encodeURIComponent(id)}`,
};
