export default function Hero() {
  return (
    <div className="w-screen h-screen relative flex flex-col items-center justify-center overflow-hidden">

      <video
        className="rounded-2xl absolute inset-0 m-auto w-[80%] pointer-events-none select-none"
        autoPlay
        loop
        muted
        playsInline
      >
        <source src="/landing.mp4" type="video/mp4" />
      </video>

      {/* Text Content */}
      <div className="bg-black/30 w-[80%] aspect-video flex items-center text-center justify-center backdrop-opacity-50 rounded-2xl py-12 px-10">
        <div>
          <div className="relative z-10 font-borel text-white text-9xl">
            verit<span className="text-[#BF5864]">ai</span>s
          </div>

          <div className="relative z-10 text-xl text-white">
            finding <span className="text-[#BF5864] font-bold">truth</span> in a world where <span className="text-[#BF5864] font-bold">deception</span> is money
          </div>
        </div>
      </div>

    </div>
  )

}
