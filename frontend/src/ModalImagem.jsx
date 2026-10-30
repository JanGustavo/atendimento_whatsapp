import { useEffect } from 'react'

export default function ModalImagem({ url, titulo, alt, onFechar }) {
  useEffect(() => {
    const aoTeclar = (evento) => {
      if (evento.key === 'Escape') onFechar?.()
    }
    window.addEventListener('keydown', aoTeclar)
    return () => window.removeEventListener('keydown', aoTeclar)
  }, [onFechar])

  if (!url) return null

  return (
    <div
      className="modal-expansao"
      role="dialog"
      aria-modal="true"
      aria-label={titulo || alt || 'Visualização ampliada'}
      onClick={onFechar}
    >
      <div className="modal-expansao-backdrop" aria-hidden="true" />
      <button
        type="button"
        className="modal-expansao-fechar"
        onClick={(evento) => {
          evento.stopPropagation()
          onFechar?.()
        }}
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
      <div className="modal-expansao-caixa" onClick={(evento) => evento.stopPropagation()}>
        <img
          src={url}
          alt={alt || titulo || 'Imagem ampliada'}
          className="modal-expansao-img"
        />
        {titulo && <p className="modal-expansao-titulo">{titulo}</p>}
      </div>
    </div>
  )
}
