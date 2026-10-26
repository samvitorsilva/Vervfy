import SwiftUI

struct GlassNavigationBar: View {
    @Binding var selectedDestination: ShellDestination
    let onNavigate: (ShellDestination) -> Void
    let onAction: (String) -> Void
    let onChangeServer: () -> Void

    @State private var showingMore = false

    private let primaryDestinations: [ShellDestination] = [
        .library, .playlists, .artists, .favorites, .account,
    ]

    var body: some View {
        HStack(spacing: 4) {
            ForEach(primaryDestinations) { destination in
                Button {
                    selectedDestination = destination
                    onNavigate(destination)
                } label: {
                    VStack(spacing: 4) {
                        Image(systemName: destination.symbol)
                            .font(.system(size: 17, weight: .medium))
                        Text(destination.title)
                            .font(.system(size: 10, weight: .medium))
                            .lineLimit(1)
                    }
                    .foregroundStyle(
                        selectedDestination == destination ? .primary : .secondary
                    )
                    .frame(maxWidth: .infinity, minHeight: 48)
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityAddTraits(
                    selectedDestination == destination ? .isSelected : []
                )
            }

            Button {
                showingMore = true
            } label: {
                VStack(spacing: 4) {
                    Image(systemName: "ellipsis")
                        .font(.system(size: 17, weight: .medium))
                    Text("More")
                        .font(.system(size: 10, weight: .medium))
                }
                .foregroundStyle(.secondary)
                .frame(maxWidth: .infinity, minHeight: 48)
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .accessibilityLabel("More options")
            .sheet(isPresented: $showingMore) {
                moreOptions
                    #if os(iOS)
                    .presentationDetents([.medium, .large])
                    #endif
            }
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 6)
        .background {
            if #available(iOS 26.0, macOS 26.0, *) {
                Capsule()
                    .fill(.clear)
                    .glassEffect(.regular, in: Capsule())
            } else {
                Capsule()
                    .fill(.ultraThinMaterial)
                    .overlay {
                        Capsule().strokeBorder(.white.opacity(0.12), lineWidth: 1)
                    }
            }
        }
    }

    private var moreOptions: some View {
        NavigationStack {
            List {
                ForEach([ShellDestination.offline, .recap]) { destination in
                    Button {
                        selectedDestination = destination
                        onNavigate(destination)
                        showingMore = false
                    } label: {
                        Label(destination.title, systemImage: destination.symbol)
                    }
                }

                Button {
                    showingMore = false
                    onAction("addMusic")
                } label: {
                    Label("Add music", systemImage: "plus")
                }

                Button {
                    showingMore = false
                    onAction("shortcuts")
                } label: {
                    Label("Keyboard shortcuts", systemImage: "keyboard")
                }

                Button(role: .destructive) {
                    showingMore = false
                    onAction("logout")
                } label: {
                    Label("Log out", systemImage: "rectangle.portrait.and.arrow.right")
                }

                Button {
                    showingMore = false
                    onChangeServer()
                } label: {
                    Label("Change server", systemImage: "server.rack")
                }
            }
            .navigationTitle("More")
            #if os(iOS)
            .navigationBarTitleDisplayMode(.inline)
            #endif
        }
    }
}
