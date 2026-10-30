let unsaved = false;
export function markUnsaved(value: boolean) { unsaved = value; }
export function confirmNavigation() { return !unsaved || window.confirm('Leave without saving your changes?'); }
