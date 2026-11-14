import Foundation

enum ShellDestination: String, CaseIterable, Identifiable {
    case library
    case offline
    case playlists
    case recap
    case artists
    case favorites
    case account

    var id: String { rawValue }

    var title: String {
        switch self {
        case .library: "Library"
        case .offline: "Offline"
        case .playlists: "Playlists"
        case .recap: "Recap"
        case .artists: "Artists"
        case .favorites: "Favorites"
        case .account: "Account"
        }
    }

    var symbol: String {
        switch self {
        case .library: "music.note.list"
        case .offline: "arrow.down.circle"
        case .playlists: "square.stack"
        case .recap: "clock"
        case .artists: "music.mic"
        case .favorites: "heart"
        case .account: "person.crop.circle"
        }
    }
}
