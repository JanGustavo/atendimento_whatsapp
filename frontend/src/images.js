export async function converterWebp(arquivo, maximo = 1600) {
  if (arquivo.size > 12 * 1024 * 1024) throw new Error('Escolha uma imagem de até 12 MB.')
  const origem = await createImageBitmap(arquivo)
  try {
    const escala = Math.min(1, maximo / Math.max(origem.width, origem.height))
    const tela = document.createElement('canvas')
    tela.width = Math.max(1, Math.round(origem.width * escala))
    tela.height = Math.max(1, Math.round(origem.height * escala))
    tela.getContext('2d').drawImage(origem, 0, 0, tela.width, tela.height)
    const webp = await new Promise(resolve => tela.toBlob(resolve, 'image/webp', 0.78))
    if (!webp || webp.type !== 'image/webp' || webp.size > 2 * 1024 * 1024) {
      throw new Error('Não foi possível preparar a imagem em WebP (limite de 2 MB).')
    }
    return webp
  } finally {
    origem.close()
  }
}
