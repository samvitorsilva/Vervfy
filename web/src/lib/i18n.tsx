"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useSyncExternalStore, type ReactNode } from "react";

export type Language = "en" | "pt-BR";

const translations: Record<string, string> = {
  "Welcome back": "Bem-vindo de volta",
  "Create your account": "Crie sua conta",
  "Log in to reach your synced library.": "Entre para acessar sua biblioteca sincronizada.",
  "Your library, uploads, and covers will be synced to it.": "Sua biblioteca, seus arquivos e capas serão sincronizados.",
  Username: "Nome de usuário",
  "Email (optional, not used to sign in)": "E-mail (opcional, não usado para entrar)",
  Password: "Senha",
  "Logging in…": "Entrando…",
  "Creating account…": "Criando conta…",
  "Log in": "Entrar",
  "Create account": "Criar conta",
  "No account yet? ": "Ainda não tem uma conta? ",
  "Already have an account? ": "Já tem uma conta? ",
  "Create one": "Criar uma",
  "Could not load the form.": "Não foi possível carregar o formulário.",
  "The authentication request could not be completed.": "Não foi possível concluir a solicitação de autenticação.",
  "Your personal music library.": "Sua biblioteca pessoal de música.",
  "Email address": "Endereço de e-mail",
  "Save email": "Salvar e-mail",
  "Clear email": "Remover e-mail",
  "Change password": "Alterar senha",
  "Update password": "Atualizar senha",
  Session: "Sessão",
  "Sign out of all devices": "Sair de todos os dispositivos",
  "Delete account": "Excluir conta",
  "Permanently removes your profile, music files, playlists, favorites, and saved lyrics. This cannot be undone.": "Remove permanentemente seu perfil, arquivos de música, playlists, favoritos e letras salvas. Esta ação não pode ser desfeita.",
  "Profile photo": "Foto do perfil",
  "Choose a photo, adjust its zoom and position, then save.": "Escolha uma foto, ajuste o zoom e a posição e salve.",
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
  "Try another title, artist, or album name.": "Tente outro título, artista ou nome de álbum.",
  "Clear search": "Limpar busca",
  "This playlist is empty": "Esta playlist está vazia",
  "Add from library": "Adicionar da biblioteca",
  "Add music": "Adicionar música",
  "No offline songs yet": "Ainda não há músicas offline",
  "Download songs from the library menu to listen without an internet connection.": "Baixe músicas pelo menu da biblioteca para ouvir sem conexão com a internet.",
  "Browse library": "Explorar biblioteca",
  "Your library is empty": "Sua biblioteca está vazia",
  "Add songs or a folder. Vervfy saves them to your account so they are available on your other devices.": "Adicione músicas ou uma pasta. O Vervfy salva tudo na sua conta para acessar em outros dispositivos.",
  "Add folder": "Adicionar pasta",
  "No favorites yet": "Ainda não há favoritos",
  "Use the heart on any song to keep it close. Your favorites sync with your account.": "Toque no coração de uma música para adicioná-la aos favoritos. Eles são sincronizados com sua conta.",
  "Nothing here yet": "Nada por aqui ainda",
  "Your library will show up here when you add music.": "Sua biblioteca aparecerá aqui quando você adicionar músicas.",
  "PLAYING FROM": "TOCANDO DE",
  Lyrics: "Letras",
  Queue: "Fila",
  "Music server unavailable": "Servidor de música indisponível",
  "Retry connection": "Tentar novamente",
  "Loading library": "Carregando biblioteca",
  "View mode": "Modo de visualização",
  "Grid view": "Visualização em grade",
  "List view": "Visualização em lista",
  "Open account": "Abrir conta",
  "Search playlists": "Buscar playlists",
  "Search library": "Buscar na biblioteca",
  "Search": "Buscar",
  "Add songs from your library to start building it.": "Adicione músicas da sua biblioteca para começar a montar sua playlist.",
  "Add music to your library, then come back to build this playlist.": "Adicione músicas à sua biblioteca e volte para montar esta playlist.",
  "No playlists found": "Nenhuma playlist encontrada",
  "Your playlists start here": "Suas playlists começam aqui",
  "Try a different name or clear your search.": "Tente outro nome ou limpe sua busca.",
  "Collect songs into playlists for every mood and moment.": "Reúna músicas em playlists para cada momento e humor.",
  "PLAYLIST": "PLAYLIST",
  song: "música",
  songs: "músicas",
  "in this collection": "nesta coleção",
  "Rename playlist": "Renomear playlist",
  "Add track to playlist": "Adicionar faixa à playlist",
  "Add tracks to playlist": "Adicionar faixas à playlist",
  "No tracks match your search.": "Nenhuma faixa corresponde à busca.",
  "Every song in your library is already in this playlist.": "Todas as músicas da biblioteca já estão nesta playlist.",
  "Create a playlist first.": "Crie uma playlist primeiro.",
  "Nothing playing": "Nada tocando",
  "Pick a track": "Escolha uma faixa",
  "Audio visualizer": "Visualizador de áudio",
  "Close visualizer": "Fechar visualizador",
  "Add songs": "Adicionar músicas",
  "Add songs from library": "Adicionar músicas da biblioteca",
  "Remove offline download": "Remover download offline",
  "Download for offline": "Baixar para ouvir offline",
  "Saving offline…": "Salvando para ouvir offline…",
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
  "No lyrics": "Sem letras",
  "Close mini player": "Fechar mini player",
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
  "Add lyrics before syncing them.": "Adicione as letras antes de sincronizá-las.",
  "Lyrics must be tapped in song order. Correct the out-of-order line.": "As letras devem ser marcadas na ordem da música. Corrija a linha fora de ordem.",
  "Lyrics synced to the track.": "Letras sincronizadas com a faixa.",
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
  "Mini player": "Mini player",
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
  "Add songs to see their artists here.": "Adicione músicas para ver os artistas aqui.",
  "This artist no longer has songs in your library.": "Este artista não tem mais músicas na sua biblioteca.",
  "Searching for lyrics…": "Buscando letras…",
  "Save lyrics": "Salvar letras",
  "Up next": "A seguir",
  "Close queue": "Fechar fila",
  "Play from start": "Tocar desde o início",
  "Your files are uploaded to your account.": "Seus arquivos serão enviados para sua conta.",
  "Drop to add music": "Solte para adicionar músicas",
  "NOW PLAYING": "TOCANDO AGORA",
  "Edit lyrics": "Editar letras",
  "Sync lyrics to audio": "Sincronizar letras com o áudio",
  "Start playback, then tap each line when it is sung.": "Inicie a reprodução e toque em cada linha quando ela for cantada.",
  "Tap at this line": "Toque nesta linha",
  Back: "Voltar",
  "Save synced lyrics": "Salvar letras sincronizadas",
  "Add lyrics": "Adicionar letras",
  "Saving…": "Salvando…",
  "Checking LRCLIB for a match.": "Procurando correspondências no LRCLIB.",
  "No lyrics available": "Letras indisponíveis",
  "Vervfy could not find lyrics for this track. Add your own below.": "O Vervfy não encontrou as letras desta faixa. Adicione-as abaixo.",
  "Paste lyrics": "Colar letras",
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
  "Email is account information only; sign in with your username.": "O e-mail é apenas informação da conta; entre com seu nome de usuário.",
  "Current password": "Senha atual",
  "New password (min 8 characters)": "Nova senha (mín. 8 caracteres)",
  "Type DELETE to confirm": "Digite DELETE para confirmar",
  "Choose another photo": "Escolher outra foto",
  "Choose photo": "Escolher foto",
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
  "Paste plain lyrics or timestamped LRC lyrics here…": "Cole as letras simples ou no formato LRC com marcações de tempo aqui…",
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
  "Open full lyrics": "Abrir letras completas",
  "Synced to playback": "Sincronizadas com a reprodução",
  "Plain lyrics": "Letras sem sincronização",
  "Couldn't load lyrics. Tap to retry.": "Não foi possível carregar as letras. Toque para tentar novamente.",
  "No lyrics found for this track.": "Nenhuma letra encontrada para esta faixa.",
  "Finding lyrics…": "Buscando letras…",
  "Name": "Nome",
  "No matches": "Nenhum resultado",
  "Genre": "Gênero",
  "Style": "Estilo",
  "Mood": "Clima",
  "Formed": "Formado em",
  "Label": "Gravadora",
  "Followers": "Seguidores",
  "Popularity": "Popularidade",
  "Verified artist information": "Informações verificadas do artista",
  "Looking up artist details…": "Buscando informações do artista…",
  "No verified artist information is available yet.": "Ainda não há informações verificadas disponíveis sobre este artista.",
  "Options for": "Opções de",
  "Shortcuts (?)": "Atalhos (?)",
  "Added to": "Adicionado a",
  "Delete playlist": "Excluir playlist",
  "Upload your files": "Envie seus arquivos",
  "Try a different search term.": "Tente buscar por outro termo.",
  "Artist not found": "Artista não encontrado",
  "Back to artists": "Voltar aos artistas",
  Artist: "Artista",
  "Play artist": "Tocar artista",
  "Play time": "Tempo de reprodução",
  About: "Sobre",
  Source: "Fonte",
  "Source page ↗": "Página da fonte ↗",
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
