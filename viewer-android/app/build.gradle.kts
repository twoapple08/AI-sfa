plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.aisfa.viewer"
    compileSdk = 35
    defaultConfig {
        applicationId = "com.aisfa.viewer"
        minSdk = 26
        targetSdk = 35
        versionCode = 3
        versionName = "0.3"
    }
    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("debug")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
}

android.testOptions.unitTests.isIncludeAndroidResources = true
android.testOptions.unitTests.all {
    // 서버에서 maven 직접 내려받기가 막힐 때: SFA_ROBO_DIR에 android-all 계열 jar를 두고 오프라인으로 쓴다
    System.getenv("SFA_ROBO_DIR")?.let { d ->
        it.systemProperty("robolectric.offline", "true")
        it.systemProperty("robolectric.dependency.dir", d)
    }
    it.environment("SFA_TEST_DIR", System.getenv("SFA_TEST_DIR") ?: "")
    it.environment("SFA_OUT_DIR", System.getenv("SFA_OUT_DIR") ?: "")
    it.environment("SFA_FRAMES", System.getenv("SFA_FRAMES") ?: "")
    it.maxHeapSize = "3g"
}

dependencies {
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.robolectric:robolectric:4.14.1")
}
