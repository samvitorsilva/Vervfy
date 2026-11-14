import SwiftUI

struct ServerSetupView: View {
    let initialAddress: String
    let onConnect: (URL) -> Void

    @State private var address = ""
    @State private var errorMessage: String?

    var body: some View {
        VStack(spacing: 22) {
            Image(systemName: "music.note")
                .font(.system(size: 34, weight: .medium))
                .foregroundStyle(.tint)
                .frame(width: 72, height: 72)
                .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 22))

            VStack(spacing: 8) {
                Text("Connect to Vervfy")
                    .font(.largeTitle.weight(.bold))
                Text("Enter the web address of your Vervfy server.")
                    .font(.body)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
            }

            VStack(alignment: .leading, spacing: 8) {
                serverAddressField
                    .onSubmit(connect)
                    .padding(14)
                    .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 14))

                if let errorMessage {
                    Text(errorMessage)
                        .font(.footnote)
                        .foregroundStyle(.red)
                }
            }

            Button(action: connect) {
                Text("Connect")
                    .font(.headline)
                    .frame(maxWidth: .infinity, minHeight: 48)
            }
            .buttonStyle(.borderedProminent)
            .disabled(address.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
        }
        .padding(28)
        .frame(maxWidth: 440)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .onAppear { address = initialAddress }
    }

    private var serverAddressField: some View {
        #if os(iOS)
        TextField("https://music.example.com", text: $address)
            .textContentType(.URL)
            .keyboardType(.URL)
            .textInputAutocapitalization(.never)
            .autocorrectionDisabled()
        #else
        TextField("https://music.example.com", text: $address)
        #endif
    }

    private func connect() {
        guard let url = ServerAddress.parse(address) else {
            errorMessage = "Enter a valid HTTPS server address."
            return
        }
        errorMessage = nil
        onConnect(url)
    }
}

enum ServerAddress {
    static func parse(_ value: String) -> URL? {
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return nil }

        let input = trimmed.contains("://") ? trimmed : "https://\(trimmed)"
        guard
            var components = URLComponents(string: input),
            let scheme = components.scheme?.lowercased(),
            let host = components.host?.lowercased(),
            components.user == nil,
            components.password == nil,
            components.query == nil,
            components.fragment == nil
        else {
            return nil
        }

        let localHosts: Set<String> = ["localhost", "127.0.0.1", "::1"]
        guard scheme == "https" || (scheme == "http" && localHosts.contains(host)) else {
            return nil
        }

        components.scheme = scheme
        return components.url
    }
}
