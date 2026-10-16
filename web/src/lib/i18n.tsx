"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useSyncExternalStore, type ReactNode } from "react";

export type Language = "en" | "pt-BR";

const translations: Record<string, string> = {
  "Welcome back": "Que bom ter você de volta!",
  "Create your account": "Crie sua conta",
  "Log in to reach your synced library.": "Entre para acessar sua biblioteca em todos os seus dispositivos.",
  "Your library, uploads, and covers will be synced to it.": "Suas músicas e capas ficam sincronizadas em todos os seus dispositivos.",
  Username: "Nome de usuário",
  "Email (optional, not used to sign in)": "E-mail (opcional; você entra com seu nome de usuário)",
  Password: "Senha",
  "Logging in…": "Entrando…",
  "Creating account…": "Criando conta…",
  "Log in": "Entrar",
  "Create account": "Criar conta",
  "No account yet? ": "Ainda não tem uma conta? ",
  "Already have an account? ": "Já tem uma conta? ",
  "Create one": "Criar conta",
  "Could not load the form.": "Não foi possível carregar o formulário.",
  "The authentication request could not be completed.": "Não foi possível concluir o login. Tente novamente.",
  "Your personal music library.": "Sua coleção pessoal de músicas.",
  "Email address": "Endereço de e-mail",
  "Save email": "Salvar e-mail",
  "Clear email": "Remover e-mail",
  "Change password": "Alterar senha",
  "Update password": "Atualizar senha",
  Session: "Sessão",
  "Sign out of all devices": "Sair de todos os dispositivos",
  "Delete account": "Excluir conta",
  "Permanently removes your profile, music files, playlists, favorites, and saved lyrics. This cannot be undone.": "Seu perfil, suas músicas, playlists, favoritos e letras salvas serão excluídos de vez. Não é possível desfazer essa ação.",
  "Profile photo": "Foto do perfil",
  "Choose a photo, adjust its zoom and position, then save.": "Escolha uma foto, ajuste o zoom e o enquadramento e salve.",
  Close: "Fechar",
  Zoom: "Zoom",
  "Language": "Idioma",
  "Choose the language used by Vervfy.": "Escolha o idioma usado pelo Vervfy.",
  English: "Inglês",
  "Português (Brasil)": "Português (Brasil)",
  Library: "Biblioteca",
  Offline: "Offline",
  Favorites: "Favoritos",
  Playlists: "Playlists",
  Artists: "Artistas",
  Account: "Conta",
  "Play next": "Tocar em seguida",
  "Add to queue": "Adicionar à fila",
  "Add to playlist": "Adicionar à playlist",
  "Share song": "Compartilhar música",
  "Try another title, artist, or album name.": "Busque por outro título, artista ou álbum.",
  "Clear search": "Limpar busca",
  "This playlist is empty": "Esta playlist está vazia",
  "Add from library": "Adicionar da biblioteca",
  "Add music": "Adicionar música",
  "No offline songs yet": "Você ainda não baixou nenhuma música.",
  "Download songs from the library menu to listen without an internet connection.": "Baixe músicas pelo menu da biblioteca para ouvir mesmo sem internet.",
  "Browse library": "Explorar biblioteca",
  "Your library is empty": "Sua biblioteca está vazia",
  "Add songs or a folder. Vervfy saves them to your account so they are available on your other devices.": "Adicione músicas ou uma pasta. O Vervfy salva tudo na sua conta para você ouvir em outros dispositivos.",
  "Add folder": "Adicionar pasta",
  "No favorites yet": "Você ainda não favoritou nenhuma música.",
  "Use the heart on any song to keep it close. Your favorites sync with your account.": "Toque no coração de uma música para adicioná-la aos favoritos. Eles ficam sincronizados com sua conta.",
  "Nothing here yet": "Nada por aqui ainda",
  "Your library will show up here when you add music.": "Suas músicas vão aparecer aqui assim que você adicioná-las.",
  "PLAYING FROM": "REPRODUZINDO DE",
  Lyrics: "Letras",
  Queue: "Fila",
  "Music server unavailable": "Servidor de música indisponível",
  "Retry connection": "Conectar novamente",
  "Loading library": "Carregando sua biblioteca",
  "View mode": "Modo de visualização",
  "Grid view": "Ver em grade",
  "List view": "Ver em lista",
  "Open account": "Abrir conta",
  "Search playlists": "Buscar nas playlists",
  "Search library": "Buscar na biblioteca",
  "Search": "Buscar",
  "Add songs from your library to start building it.": "Adicione músicas da sua biblioteca para começar a criar sua playlist.",
  "Add music to your library, then come back to build this playlist.": "Adicione músicas à biblioteca e volte aqui para montar sua playlist.",
  "No playlists found": "Nenhuma playlist encontrada",
  "Your playlists start here": "Crie sua primeira playlist",
  "Try a different name or clear your search.": "Tente outro nome ou apague a busca.",
  "Collect songs into playlists for every mood and moment.": "Monte playlists para cada clima e momento.",
  "PLAYLIST": "PLAYLIST",
  song: "música",
  songs: "músicas",
  "in this collection": "nesta coleção",
  "Rename playlist": "Renomear playlist",
  "Add track to playlist": "Adicionar faixa à playlist",
  "Add tracks to playlist": "Adicionar faixas à playlist",
  "No tracks match your search.": "Nenhuma faixa corresponde à busca.",
  "Every song in your library is already in this playlist.": "Esta playlist já tem todas as músicas da sua biblioteca.",
  "Create a playlist first.": "Crie uma playlist para começar.",
  "Nothing playing": "Nada tocando",
  "Pick a track": "Escolha uma faixa",
  "Audio visualizer": "Visualizador de áudio",
  "Close visualizer": "Fechar visualizador",
  "Add songs": "Adicionar músicas",
  "Add songs from library": "Adicionar músicas da biblioteca",
  "Remove offline download": "Remover download offline",
  "Download for offline": "Baixar para ouvir sem internet",
  "Saving offline…": "Baixando para ouvir sem internet…",
  "Remove from liked songs": "Remover das músicas curtidas",
  "Save to liked songs": "Salvar nas músicas curtidas",
  "Remove from this playlist": "Remover desta playlist",
  "Remove from library": "Remover da biblioteca",
  "All playlists": "Todas as playlists",
  "Your queue is empty.": "Sua fila está vazia.",
  "Playlist name": "Nome da playlist",
  "New playlist": "Nova playlist",
  "Save": "Salvar",
  "Create": "Criar",
  "Cancel": "Cancelar",
  "No lyrics": "Sem letra disponível",
  "Previous track": "Faixa anterior",
  "Next track": "Próxima faixa",
  "Play or pause": "Tocar ou pausar",
  "Remove from queue": "Remover da fila",
  "Drag to reorder": "Arraste para reordenar",
  "tracks": "faixas",
  "Close shortcuts": "Fechar atalhos",
  "Space": "Espaço",
  "No songs match your search.": "Nenhuma música corresponde à busca.",
  "Playback": "Reprodução",
  "Lyrics saved.": "Letras salvas.",
  "Paste some lyrics first.": "Cole as letras primeiro.",
  "Add lyrics before syncing them.": "Adicione a letra da música antes de sincronizá-la.",
  "Lyrics must be tapped in song order. Correct the out-of-order line.": "Marque as linhas na ordem em que são cantadas. Corrija a linha que ficou fora de ordem.",
  "Lyrics synced to the track.": "Letra sincronizada com a música.",
  "Create playlist": "Criar playlist",
  Playlist: "Playlist",
  Play: "Tocar",
  Rename: "Renomear",
  Delete: "Excluir",
  Songs: "Músicas",
  Albums: "Álbuns",
  min: "min",
  hr: "h",
  Title: "Título",
  Album: "Álbum",
  Time: "Duração",
  "Keyboard shortcuts": "Atalhos do teclado",
  "Play / pause": "Tocar / pausar",
  "Previous / next track": "Faixa anterior / próxima",
  "Seek 5 seconds": "Avançar ou voltar 5 segundos",
  Volume: "Volume",
  Mute: "Silenciar",
  "Favorite current track": "Favoritar música atual",
  Visualizer: "Visualizador",
  Shortcuts: "Atalhos",
  "Close panels": "Fechar painéis",
  "Main navigation": "Navegação principal",
  "Your playlists": "Suas playlists",
  "Could not load account.": "Não foi possível carregar a conta.",
  "Could not delete account.": "Não foi possível excluir a conta.",
  "Choose a photo before saving.": "Escolha uma foto antes de salvar.",
  "Your browser could not prepare the photo.": "Seu navegador não conseguiu preparar a foto.",
  "Could not prepare this photo.": "Não foi possível preparar esta foto.",
  "Could not log out.": "Não foi possível sair.",
  "Logging out…": "Saindo…",
  "Log out": "Sair",
  "Loading account…": "Carregando conta…",
  "Library information": "Informações da biblioteca",
  "Add songs to see their artists here.": "Adicione músicas para encontrar seus artistas aqui.",
  "This artist no longer has songs in your library.": "Você não tem mais músicas deste artista na biblioteca.",
  "Searching for lyrics…": "Buscando letras…",
  "Save lyrics": "Salvar letras",
  "Up next": "A seguir",
  "Close queue": "Fechar fila",
  "Play from start": "Tocar desde o início",
  "Your files are uploaded to your account.": "Suas músicas ficam salvas na sua conta.",
  "Drop to add music": "Solte para adicionar músicas",
  "NOW PLAYING": "TOCANDO AGORA",
  "Edit lyrics": "Editar letras",
  "Sync lyrics to audio": "Sincronizar letras com o áudio",
  "Start playback, then tap each line when it is sung.": "Dê o play e toque em cada linha no momento em que ela for cantada.",
  "Tap at this line": "Toque nesta linha",
  Back: "Voltar",
  "Save synced lyrics": "Salvar letras sincronizadas",
  "Add lyrics": "Adicionar letras",
  "Saving…": "Salvando…",
  "Checking LRCLIB for a match.": "Procurando a letra no LRCLIB.",
  "No lyrics available": "Letra indisponível",
  "Vervfy could not find lyrics for this track. Add your own below.": "O Vervfy não encontrou a letra desta música. Se quiser, adicione-a abaixo.",
  "Paste lyrics": "Colar letra",
  "Sync to audio": "Sincronizar com o áudio",
  "Music files": "Arquivos de música",
  "Member since": "Membro desde",
  "tracks in your library": "faixas na sua biblioteca",
  "Liked songs": "Músicas curtidas",
  "saved favorites": "favoritos salvos",
  "in your library": "na sua biblioteca",
  "saved playlists": "playlists salvas",
  "Edit profile photo": "Editar foto do perfil",
  "No email on file": "Nenhum e-mail cadastrado",
  "Email is account information only; sign in with your username.": "O e-mail é apenas um dado da conta. Para entrar, use seu nome de usuário.",
  "Current password": "Senha atual",
  "New password (min 8 characters)": "Nova senha (mín. 8 caracteres)",
  "Type DELETE to confirm": "Digite DELETE para confirmar",
  "Choose another photo": "Escolher outra foto",
  "Choose a JPEG, PNG, WebP, or GIF image.": "Escolha uma imagem JPEG, PNG, WebP ou GIF.",
  "Profile photo must be 5 MB or smaller.": "A foto do perfil deve ter no máximo 5 MB.",
  "Photo will be removed when you save.": "A foto será removida quando você salvar.",
  "Choose a photo to get started.": "Escolha uma foto para começar.",
  "Could not load this photo.": "Não foi possível carregar esta foto.",
  "Photo zoom": "Zoom da foto",
  "Saving email…": "Salvando e-mail…",
  "Email saved to your account.": "E-mail salvo na sua conta.",
  "Email removed.": "E-mail removido.",
  "Could not update email.": "Não foi possível atualizar o e-mail.",
  "Updating…": "Atualizando…",
  "Password updated.": "Senha atualizada.",
  "Could not update password.": "Não foi possível atualizar a senha.",
  "Removing…": "Removendo…",
  "Profile photo removed.": "Foto do perfil removida.",
  "Could not save profile photo.": "Não foi possível salvar a foto do perfil.",
  "Profile photo saved.": "Foto do perfil salva.",
  "Could not sign out of all devices.": "Não foi possível sair de todos os dispositivos.",
  "Deleting account…": "Excluindo conta…",
  "Delete your account and all of its music data permanently?": "Excluir permanentemente sua conta e todos os dados de música?",
  "Close photo editor": "Fechar edição da foto",
  "Photo crop preview; drag to reposition": "Prévia do recorte da foto; arraste para reposicionar",
  "Close player": "Fechar player",
  "More options for": "Mais opções para",
  "More options": "Mais opções",
  "No matches for": "Nenhum resultado para",
  "Close lyrics": "Fechar letras",
  "Paste plain lyrics or timestamped LRC lyrics here…": "Cole a letra aqui, com ou sem marcações de tempo no formato LRC…",
  "Track progress": "Progresso da faixa",
  "Now playing": "Tocando agora",
  "Audio frequency visualizer": "Visualizador de frequências de áudio",
  "Lyrics (L)": "Letras (L)",
  "Visualizer (V)": "Visualizador (V)",
  "Your library is empty.": "Sua biblioteca está vazia.",
  "Shuffle on": "Modo aleatório ativado",
  "Shuffle off": "Modo aleatório desativado",
  "Remove favorite": "Remover dos favoritos",
  "Favorite": "Favoritar",
  "Shuffle": "Aleatório",
  "Pause": "Pausar",
  "Repeat: off": "Repetir: desativado",
  "Repeat: all": "Repetir: tudo",
  "Repeat: one": "Repetir: uma faixa",
  "Open full lyrics": "Abrir letra completa",
  "Synced to playback": "Sincronizada com a música",
  "Plain lyrics": "Letra sem sincronização",
  "Couldn't load lyrics. Tap to retry.": "Não foi possível carregar a letra. Toque para tentar de novo.",
  "No lyrics found for this track.": "Não encontramos a letra desta música.",
  "Finding lyrics…": "Procurando a letra…",
  "Name": "Nome",
  "No matches": "Nenhum resultado",
  "Genre": "Gênero",
  "Style": "Estilo",
  "Mood": "Clima",
  "Formed": "Ano de formação",
  "Label": "Gravadora",
  "Options for": "Opções de",
  "Shortcuts (?)": "Atalhos (?)",
  "Added to": "Adicionado a",
  "Delete playlist": "Excluir playlist",
  "Upload your files": "Envie seus arquivos",
  "Try a different search term.": "Tente buscar por outro nome.",
  "Artist not found": "Artista não encontrado",
  "Back to artists": "Voltar aos artistas",
  Artist: "Artista",
  "Play artist": "Tocar músicas do artista",
  "Play time": "Tempo total",
  About: "Sobre",
  Source: "Fonte",
  "Source: Wikipedia": "Fonte: Wikipédia",
  "Shortened or adapted": "Texto resumido ou adaptado",
  "Source page ↗": "Ver fonte ↗",
  "Open artist page": "Abrir página do artista",
  "Change image": "Alterar imagem",
  "Remove photo": "Remover foto",
  "Photo for": "Foto de",
  "Choose photo": "Escolher foto",
  "Save photo": "Salvar foto",
  "Saving photo…": "Salvando foto…",
  "Choose an artist photo.": "Escolha uma foto para o artista.",
  "Artist photo must be 5 MB or smaller.": "A foto do artista deve ter no máximo 5 MB.",
  "Could not update artist photo.": "Não foi possível atualizar a foto do artista.",
  "Could not remove artist photo.": "Não foi possível remover a foto do artista.",
  "album": "álbum",
  "albums": "álbuns",
  "Official website": "Site oficial",
  "Official artist website": "Site oficial do artista",
  "Official artist site": "Site oficial do artista",
  "Official artist page": "Página oficial do artista",
  "Official music video": "Videoclipe oficial",
  "Artist profile": "Perfil do artista",
  "No artist information is available yet.": "Ainda não há informações sobre este artista.",
  "Wikipédia": "Wikipédia",
  "MORADA artist biography": "Biografia do MORADA",
  "Marcos Nui artist profile": "Perfil de artista de Marcos Nui",
  "Tommy Bueno official artist page": "Página oficial de Tommy Bueno",
  "Vision of Leo release page": "Página do lançamento de Vision of Leo",
  "O'Bros official artist site": "Site oficial do O'Bros",
  "KALLY'S Mashup official artist channel": "Canal oficial de KALLY'S Mashup",
  "Vic Lucas official artist site and artist profile": "Site e perfil oficiais de Vic Lucas",
  "Kai Malachi official artist site and artist profile": "Site e perfil oficiais de Kai Malachi",
  "AJ Vitanza official artist site": "Site oficial de AJ Vitanza",
  "Miel San Marcos official artist site": "Site oficial de Miel San Marcos",
  "Brayden Tabakian artist profile": "Perfil de artista de Brayden Tabakian",
  "Joseph O'Brien official artist site": "Site oficial de Joseph O'Brien",
  "Strings & Heart official artist site": "Site oficial de Strings & Heart",
  "gio. official artist site": "Site oficial de gio.",
  "Change cover": "Alterar capa",
  "Add cover": "Adicionar capa",
  "Generated placeholder": "Capa ilustrativa gerada",
  "Retry cover": "Tentar capa de novo",
  "This cover will be used for each selected track.": "Esta capa será usada em cada faixa selecionada.",
  "Cover lookup queued.": "Busca de capa enfileirada.",
  "Could not retry cover lookup.": "Não foi possível tentar a capa de novo.",
  "Optional cover": "Capa opcional",
  "Cover selected": "Capa selecionada",
  "Cover art from MusicBrainz / Cover Art Archive": "Capa de MusicBrainz / Cover Art Archive",
  "MusicBrainz and Cover Art Archive": "MusicBrainz e Cover Art Archive",
  "When a track has no uploaded or embedded cover, Vervfy may link a front-cover URL from Cover Art Archive via MusicBrainz. Those covers are shown by URL only; Vervfy does not store copies of the image files.": "Quando uma faixa não tem capa enviada ou incorporada, o Vervfy pode vincular um URL de capa do Cover Art Archive via MusicBrainz. Essas capas são exibidas só pelo URL; o Vervfy não armazena cópias dos arquivos de imagem.",
  "Remove cover": "Remover capa",
  "Edit track details": "Editar detalhes da faixa",
  "Track details": "Detalhes da faixa",
  "Cover for": "Capa de",
  "Choose cover image": "Escolher imagem da capa",
  "Choose cover image.": "Escolha uma imagem para a capa.",
  "Current cover for": "Capa atual de",
  "Cover image must be 5 MB or smaller.": "A imagem da capa deve ter no máximo 5 MB.",
  "Choose a JPEG, PNG, or WebP image.": "Escolha uma imagem JPEG, PNG ou WebP.",
  "Saving cover…": "Salvando capa…",
  "Removing cover…": "Removendo capa…",
  "JPEG, PNG, or WebP; up to 5 MB.": "JPEG, PNG ou WebP; até 5 MB.",
  "Save cover": "Salvar capa",
  "Apply to all tracks of this album": "Aplicar a todas as faixas deste álbum",
  "An album name is required to apply a cover to the album.": "Informe o nome do álbum para aplicar uma capa a todas as faixas.",
  "Also replace covers you uploaded on this album": "Também substituir as capas enviadas por você neste álbum",
  "Cover updated.": "Capa atualizada.",
  "Cover removed.": "Capa removida.",
  "Could not update cover.": "Não foi possível atualizar a capa.",
  "Could not remove cover.": "Não foi possível remover a capa.",
  "Track details saved.": "Detalhes da faixa salvos.",
  "Could not update track details.": "Não foi possível atualizar os detalhes da faixa.",
  "Save changes": "Salvar alterações",
  "Credits": "Créditos",
  "Credits and data sources": "Créditos e fontes de dados",
  "Sources, licenses, and how Vervfy uses them.": "Fontes, licenças e como o Vervfy as utiliza.",
  "Artist biographies": "Biografias de artistas",
  "Wikipedia text is shortened or adapted and linked to its article.": "O texto da Wikipédia é resumido ou adaptado e inclui um link para o artigo.",
  "Artist images by TheAudioDB": "Imagens de artistas por TheAudioDB",
  "Artist image URLs and IDs are supplied by TheAudioDB. Third-party images are linked directly; Vervfy stores their URLs, not copies of the image files.": "Os IDs e URLs das imagens de artistas são fornecidos pelo TheAudioDB. As imagens de terceiros são carregadas diretamente; o Vervfy armazena os URLs, não cópias dos arquivos.",
  "API documentation": "Documentação da API",
  "Lyrics lookup": "Busca de letras",
  "LRCLIB supplies optional lyrics lookups. Results are cached only in this browser for three days and are not stored in the Vervfy database.": "O LRCLIB fornece buscas opcionais de letras. Os resultados ficam em cache apenas neste navegador por três dias e não são armazenados no banco de dados do Vervfy.",
  "Lyrics remain subject to the rights held by their respective owners; Vervfy does not claim a reproduction license.": "As letras continuam sujeitas aos direitos de seus respectivos titulares; o Vervfy não reivindica uma licença de reprodução.",
  "User-owned media": "Mídia do usuário",
  "Audio tags, embedded artwork, uploaded covers, and pasted lyrics come from your own files or account.": "As tags de áudio, capas incorporadas, capas enviadas e letras coladas vêm dos seus próprios arquivos ou conta.",
  "Back to Vervfy": "Voltar ao Vervfy",
  "Paste your own lyrics.": "Cole suas próprias letras.",
  "LRCLIB lookup is disabled.": "A busca no LRCLIB está desativada.",
  "LRCLIB disabled": "LRCLIB desativado",
  "Only your own pasted lyrics are shown.": "Somente as letras que você colou são exibidas.",
};

interface LanguageContextValue {
  language: Language;
  setLanguage: (language: Language) => void;
  t: (text: string) => string;
}

const LanguageContext = createContext<LanguageContextValue>({
  language: "en",
  setLanguage: () => undefined,
  t: (text) => text,
});

let activeLanguage: Language = "en";
const languageListeners = new Set<() => void>();

function subscribeLanguage(listener: () => void): () => void {
  languageListeners.add(listener);
  return () => languageListeners.delete(listener);
}

function currentLanguage(): Language {
  return activeLanguage;
}

function serverLanguage(): Language {
  return "en";
}

function updateLanguage(language: Language): void {
  if (activeLanguage === language) return;
  activeLanguage = language;
  for (const listener of languageListeners) listener();
}

function browserLanguage(): Language {
  if (typeof navigator === "undefined") return "en";
  const languages = navigator.languages.length ? navigator.languages : [navigator.language];
  for (const language of languages) {
    const normalized = language.toLowerCase();
    if (normalized.startsWith("pt")) return "pt-BR";
    if (normalized.startsWith("en")) return "en";
  }
  return "en";
}

export function LanguageProvider({ children }: { children: ReactNode }) {
  const language = useSyncExternalStore(subscribeLanguage, currentLanguage, serverLanguage);

  useEffect(() => {
    const saved = window.localStorage.getItem("vervfy:language");
    const initial: Language = saved === "pt-BR" ? "pt-BR" : saved === "en" ? "en" : browserLanguage();
    updateLanguage(initial);
  }, []);

  const setLanguage = useCallback((next: Language) => {
    window.localStorage.setItem("vervfy:language", next);
    updateLanguage(next);
  }, []);

  const t = useCallback(
    (text: string) => activeLanguage === "pt-BR" ? translations[text] ?? text : text,
    [],
  );

  useEffect(() => {
    document.documentElement.lang = language === "pt-BR" ? "pt-BR" : "en";
  }, [language]);

  const value = useMemo<LanguageContextValue>(
    () => ({ language, setLanguage, t }),
    [language, setLanguage, t],
  );

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useLanguage(): LanguageContextValue {
  return useContext(LanguageContext);
}

export function LanguageSelect({ className = "" }: { className?: string }) {
  const { language, setLanguage, t } = useLanguage();
  return (
    <label className={`language-select ${className}`.trim()}>
      <span>{t("Language")}</span>
      <select
        aria-label={t("Language")}
        value={language}
        onChange={(event) => setLanguage(event.currentTarget.value === "pt-BR" ? "pt-BR" : "en")}
      >
        <option value="en">English</option>
        <option value="pt-BR">Português (Brasil)</option>
      </select>
    </label>
  );
}
