// AI-sfa: Mixamo 동작 일괄 받기 (로그인한 mixamo.com 탭의 개발자 도구 콘솔에 붙여 넣기)
// 1) 먼저 aisfaProbe() 로 연결 확인 → 2) aisfaDownload() 로 받기
// - 캐릭터 없이(skin false), FBX, 30fps. 받은 파일은 브라우저 '다운로드' 폴더에 쌓인다.
// - 이미 받은 동작은 이 탭이 기억해 건너뛴다(localStorage aisfa_done). 탭을 닫아도 남는다.
// - 개인용(비상업) 학습 자료. Mixamo 이용약관 범위에서 쓴다. 받은 파일은 저장소에 넣지 않는다.
(() => {
  const API = "https://www.mixamo.com/api/v1";
  const H = () => ({
    Accept: "application/json",
    "Content-Type": "application/json",
    Authorization: "Bearer " + localStorage.access_token,
    "X-Api-Key": "mixamo2",
  });
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const get = async (u) => {
    const r = await fetch(u, { headers: H() });
    if (!r.ok) throw new Error(r.status + " " + u);
    return r.json();
  };
  const QUERIES = ["punch", "kick", "fight", "combat", "boxing", "martial", "karate", "attack", "slash", "sword",
    "block", "dodge", "hit", "reaction", "knock", "stagger", "fall", "death", "dying", "get up", "jump", "flip",
    "roll", "run", "sprint", "walk", "idle", "taunt", "throw", "dash", "slide", "crouch", "land"];

  async function characterId() {
    for (const u of [API + "/characters/primary"]) {
      try {
        const j = await get(u);
        const id = j.primary_character_id || j.character_id || j.id;
        if (id) return id;
      } catch (e) { console.log("캐릭터 조회 실패", e.message); }
    }
    return null;
  }

  async function listAll(query) {
    const out = [];
    for (let page = 1; page < 50; page++) {
      const j = await get(`${API}/products?page=${page}&limit=96&order=&type=Motion&query=${encodeURIComponent(query)}`);
      out.push(...(j.results || []));
      if (!j.pagination || page >= j.pagination.num_pages) break;
    }
    return out;
  }

  async function exportOne(cid, anim) {
    const p = await get(`${API}/products/${anim.id}?similar=0&character_id=${cid}`);
    const gh = p.details.gms_hash;
    const gms = Object.assign({}, gh, { params: (gh.params || []).map((x) => x[1]).join(",") });
    const body = { character_id: cid, gms_hash: [gms], product_name: anim.name, type: "Motion",
      preferences: { format: "fbx7", skin: "false", fps: "30", reducekf: "0" } };
    const r = await fetch(`${API}/animations/export`, { method: "POST", headers: H(), body: JSON.stringify(body) });
    if (!r.ok) throw new Error("export " + r.status);
    for (let i = 0; i < 60; i++) {
      await sleep(1500);
      const m = await get(`${API}/characters/${cid}/monitor`);
      if (m.status === "completed") return m.job_result;
      if (m.status === "failed") throw new Error("monitor failed");
    }
    throw new Error("시간 초과");
  }

  async function save(url, name) {
    const b = await (await fetch(url)).blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(b);
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 5000);
  }

  window.aisfaProbe = async () => {
    console.log("토큰 있음:", !!localStorage.access_token);
    const cid = await characterId();
    console.log("캐릭터 id:", cid);
    const res = await listAll("punch");
    console.log("punch 검색 결과:", res.length, res.slice(0, 3).map((x) => x.name));
    if (cid && res.length) {
      const url = await exportOne(cid, res[0]);
      console.log("시험 내보내기 성공:", res[0].name);
      await save(url, `mixamo_TEST_${res[0].id}.fbx`);
      console.log("다운로드 폴더에 mixamo_TEST_… 파일이 생겼는지 확인. 되면 aisfaDownload() 실행");
    }
  };

  window.aisfaDownload = async (queries = QUERIES) => {
    const cid = await characterId();
    if (!cid) return console.log("캐릭터 id를 못 찾음. aisfaProbe() 결과를 Claude에게 보낼 것");
    const done = new Set(JSON.parse(localStorage.aisfa_done || "[]"));
    const seen = new Map();
    for (const q of queries) {
      try {
        for (const a of await listAll(q)) if (!seen.has(a.id)) seen.set(a.id, { ...a, q });
      } catch (e) { console.log("검색 실패", q, e.message); }
      console.log("검색", q, "누적", seen.size);
    }
    const todo = [...seen.values()].filter((a) => !done.has(a.id));
    console.log("받을 동작", todo.length, "(이미 받음", done.size, ")");
    const index = [];
    let k = 0;
    for (const a of todo) {
      k++;
      try {
        const url = await exportOne(cid, a);
        const safe = a.name.replace(/[^\w\- ]+/g, "").trim().replace(/\s+/g, "_");
        await save(url, `mixamo_${safe}_${a.id}.fbx`);
        done.add(a.id);
        localStorage.aisfa_done = JSON.stringify([...done]);
        index.push([a.id, a.name, a.q, (a.description || "").replace(/[\r\n,]+/g, " ")].join(","));
        console.log(`${k}/${todo.length}`, a.name);
      } catch (e) { console.log("실패", a.name, e.message); await sleep(3000); }
      await sleep(800);
    }
    const csv = "id,name,query,description\n" + index.join("\n");
    await save(URL.createObjectURL(new Blob([csv], { type: "text/csv" })), "mixamo_index.csv");
    console.log("끝. 다운로드 폴더의 mixamo_*.fbx 와 mixamo_index.csv");
  };
  console.log("준비됨: aisfaProbe() 먼저 실행");
})();
