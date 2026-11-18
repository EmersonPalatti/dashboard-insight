import { LIGHT } from "../theme";

/** Logo "Carimbo Nº" (frontend/public/favicon.svg): recibo picotado com Nº sobre quadrado vinho. */
export const Logo = ({ size = 96, background = LIGHT.wine }: { readonly size?: number; readonly background?: string }) => (
  <svg width={size} height={size} viewBox="0 0 32 32">
    <rect width="32" height="32" rx="6" fill={background} />
    <g
      transform="translate(16 16) scale(0.84) translate(-16 -16)"
      fill="none"
      stroke="#F2E6EA"
      strokeWidth="2.2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M3 9Q3 5 7 5H25Q29 5 29 9V23L28 25L24 27L20 25L16 27L12 25L8 27L4 25L3 23Z" />
      <path d="M7 23V9L15 23V9" />
      <circle cx="22.5" cy="11.5" r="2" />
      <path d="M19.5 18.5H25.5" />
    </g>
  </svg>
);
