import SwiftUI

struct ContentView: View {
    @AppStorage("vervfy.serverURL")
    private var savedServerURL = "https://vervfy-one.vercel.app/"
    @State private var selectedDestination = ShellDestination.library
    @State private var navigationIsVisible = false
    @State private var webViewController = WebViewController()

    private var serverURL: URL? {
        ServerAddress.parse(savedServerURL)
    }

    var body: some View {
        Group {
            if let serverURL {
                VervfyWebView(
                    url: serverURL,
                    selectedDestination: $selectedDestination,
                    navigationIsVisible: $navigationIsVisible,
                    controller: webViewController
                )
                .overlay(alignment: .topTrailing) {
                    if !navigationIsVisible {
                        Button {
                            savedServerURL = ""
                        } label: {
                            Image(systemName: "server.rack")
                                .frame(width: 44, height: 44)
                        }
                        .buttonStyle(.bordered)
                        .padding(12)
                        .accessibilityLabel("Change server")
                    }
                }
                .safeAreaInset(edge: .bottom, spacing: 0) {
                    if navigationIsVisible {
                        GlassNavigationBar(
                            selectedDestination: $selectedDestination,
                            onNavigate: { webViewController.navigate(to: $0) },
                            onAction: { webViewController.perform($0) },
                            onChangeServer: { savedServerURL = "" }
                        )
                        .padding(.horizontal, 16)
                        .padding(.top, 8)
                        .padding(.bottom, 6)
                    }
                }
            } else {
                ServerSetupView(initialAddress: savedServerURL) { url in
                    savedServerURL = url.absoluteString
                }
            }
        }
        .preferredColorScheme(.dark)
        #if os(macOS)
        .frame(minWidth: 720, minHeight: 520)
        #endif
    }
}
