export function Feedback({ message, success = false }: { message: string; success?: boolean }) {
  return <div className={`feedback ${success ? 'success' : 'error'}`} role={success ? 'status' : 'alert'}>{message}</div>;
}
