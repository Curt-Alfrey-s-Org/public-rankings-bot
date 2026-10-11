//
//  MainTabView.swift
//  Pro Billards Software
//

import SwiftUI

struct MainTabView: View {
    var body: some View {
        TabView {
            Text("Home")
                .tabItem { Label("Home", systemImage: "house") }
            RankingsView()
                .tabItem { Label("Rankings", systemImage: "list.number") }
            Text("Events")
                .tabItem { Label("Events", systemImage: "calendar") }
            SettingsTabView()
                .tabItem { Label("Settings", systemImage: "gear") }
        }
    }
}

struct SettingsTabView: View {
    @ObservedObject private var auth = AuthState.shared

    var body: some View {
        VStack(spacing: 16) {
            Text("Settings")
                .font(.title2)
            Button("Log out") {
                auth.logout()
            }
            .buttonStyle(.borderedProminent)
        }
        .padding()
    }
}
