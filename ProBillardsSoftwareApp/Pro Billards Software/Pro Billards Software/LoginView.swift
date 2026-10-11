//
//  LoginView.swift
//  Pro Billards Software
//

import SwiftUI

struct LoginView: View {
    @ObservedObject private var auth = AuthState.shared
    @State private var username = ""
    @State private var password = ""
    @State private var errorMessage: String?
    @State private var isLoading = false

    var body: some View {
        ScrollView {
            VStack(spacing: 20) {
                Text("Pro Billards Software")
                    .font(.title2)
                    .fontWeight(.semibold)
                    .padding(.top, 40)

                TextField("Username", text: $username)
                    .textFieldStyle(.roundedBorder)
                    .textContentType(.username)

                SecureField("Password", text: $password)
                    .textFieldStyle(.roundedBorder)
                    .textContentType(.password)

                if let msg = errorMessage {
                    Text(msg)
                        .font(.caption)
                        .foregroundStyle(.red)
                        .multilineTextAlignment(.center)
                }

                Button(action: performLogin) {
                    if isLoading {
                        ProgressView()
                            .progressViewStyle(CircularProgressViewStyle(tint: .white))
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 12)
                    } else {
                        Text("Log in")
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 12)
                    }
                }
                .buttonStyle(.borderedProminent)
                .disabled(username.isEmpty || password.isEmpty || isLoading)
                .padding(.top, 8)
            }
            .padding(.horizontal, 24)
        }
    }

    private func performLogin() {
        errorMessage = nil
        isLoading = true
        Task {
            do {
                let (token, _, _) = try await APIClient.login(username: username, password: password)
                await MainActor.run {
                    auth.didLogin(token: token)
                    isLoading = false
                }
            } catch {
                await MainActor.run {
                    errorMessage = error.localizedDescription
                    isLoading = false
                }
            }
        }
    }
}
