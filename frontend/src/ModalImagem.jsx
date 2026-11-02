import { useEffect, useRef } from 'react'

export default function ModalImagem({ url, titulo, alt, onFechar }) {
  const caixaRef = useRef(null)
  const fecharRef = useRef(null)
  const onFecharRef = useRef(onFechar)
  onFecharRef.current = onFechar

  useEffect(() => {
    if (!url) return undefined
    const focoAnterior = document.activeElement
    const frame = window.requestAnimationFrame(() => fecharRef.current?.focus())

    const aoTeclar = (evento) => {
      if (evento.key === 'Escape') {
        evento.preventDefault()
        onFecharRef.current?.()
        return
      }
      if (evento.key !== 'Tab') return
      const focaveis = caixaRef.current?.querySelectorAll(
        'button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
      )
      if (!focaveis?.length) {
        evento.preventDefault()
        caixaRef.current?.focus()
        return
      }
      const primeiro = focaveis[0]
      const ultimo = focaveis[focaveis.length - 1]
      if (evento.shiftKey && document.activeElement === primeiro) {
        evento.preventDefault()
        ultimo.focus()
      } else if (!evento.shiftKey && document.activeElement === ultimo) {
        evento.preventDefault()
        primeiro.focus()
      }
    }

    window.addEventListener('keydown', aoTeclar)
    return () => {
      window.cancelAnimationFrame(frame)
      window.removeEventListener('keydown', aoTeclar)
      if (focoAnterior instanceof HTMLElement && focoAnterior.isConnected) focoAnterior.focus()
    }
  }, [url])

  if (!url) return null

  return (
    <div
      ref={caixaRef}
      className="modal-expansao"
      role="dialog"
      aria-modal="true"
      aria-label={titulo || alt || 'Visualização ampliada'}
      tabIndex={-1}
    >
      <button
        type="button"
        className="modal-expansao-backdrop"
        onClick={() => onFechar?.()}
        aria-label="Fechar visualização da imagem"
      />
      <div className="modal-expansao-caixa">
        <button
          ref={fecharRef}
          type="button"
          className="modal-expansao-fechar"
          onClick={() => onFechar?.()}
          aria-label="Fechar visualização"
          title="Fechar (Esc)"
        >
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
        <img src={url} alt={alt || titulo || 'Imagem ampliada'} className="modal-expansao-img" />
        {titulo && <p className="modal-expansao-titulo">{titulo}</p>}
      </div>
    </div>
  )
}
