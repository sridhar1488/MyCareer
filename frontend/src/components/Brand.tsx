export function Brand({ inverse = false, showProduct = true }: { inverse?: boolean; showProduct?: boolean }) {
  const logo = import.meta.env.VITE_CORPORATE_LOGO_URL || (inverse
    ? 'https://medimpactinternational.com/wp-content/uploads/2026/03/MedImpact-International-Clear-Background.webp'
    : '');
  return <div className={`brand ${inverse ? 'brand-inverse' : ''}`}>
    {logo ? <img className="corporate-logo" src={logo} alt="MedImpact International" />
      : <span className="corporate-name">MedImpact <span>International</span></span>}
    {showProduct && <>
      <span className="brand-divider" aria-hidden="true" />
      <span className="product-name">MyCareer</span>
    </>}
  </div>;
}
