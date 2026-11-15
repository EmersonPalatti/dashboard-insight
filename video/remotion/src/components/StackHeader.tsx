import type { CSSProperties } from "react";
import { STACK } from "../data";
import { NUM, SIDE, SLAB } from "../theme";
import { useTokens } from "../theme";

/** "COMANDAS ABERTAS · 6" no topo da pilha (cenas 3 e 4). Mesma posição nas duas cenas. */
export const StackHeader = ({ style }: { readonly style?: CSSProperties }) => {
  const t = useTokens();
  return (
    <div
      style={{
        position: "absolute",
        left: SIDE,
        top: STACK.headerTop,
        fontFamily: SLAB,
        fontWeight: 700,
        fontSize: 30,
        lineHeight: "36px",
        letterSpacing: "0.03em",
        color: t.ink,
        ...NUM,
        ...style,
      }}
    >
      COMANDAS ABERTAS · 6
    </div>
  );
};
