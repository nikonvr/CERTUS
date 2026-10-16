; ModuleID = 'compute_batch_rmse'
source_filename = "<string>"
target datalayout = "e-m:e-p270:32:32-p271:32:32-p272:64:64-i64:64-i128:128-f80:128-n8:16:32:64-S128"
target triple = "x86_64-pc-windows-msvc"

@printf_format = internal constant [17 x i8] c"num_threads: %d\0A\00"
@.const.pickledata.9d8bd6d541b3e336fd7917994940781bc68a3a8a = internal constant [112 x i8] c"\80\04\95e\00\00\00\00\00\00\00\8C\08builtins\94\8C\0CRuntimeError\94\93\94\8C@Invalid number of threads. This likely indicates a bug in Numba.\94\85\94N\87\94."
@.const.pickledata.9d8bd6d541b3e336fd7917994940781bc68a3a8a.sha1 = internal constant [20 x i8] c"\9D\8B\D6\D5A\B3\E36\FDy\17\99I@x\1B\C6\8A:\8A"
@.const.picklebuf.9d8bd6d541b3e336fd7917994940781bc68a3a8a = internal constant { ptr, i32, ptr, ptr, i32 } { ptr @.const.pickledata.9d8bd6d541b3e336fd7917994940781bc68a3a8a, i32 112, ptr @.const.pickledata.9d8bd6d541b3e336fd7917994940781bc68a3a8a.sha1, ptr null, i32 0 }
@printf_format.1 = internal constant [17 x i8] c"num_threads: %d\0A\00"
@.const.compute_batch_rmse = internal constant [19 x i8] c"compute_batch_rmse\00"
@_ZN08NumbaEnv6certus7physics18certus_strat_batch18compute_batch_rmseB2v1B126c8tJTC_2fWQAliW1xhDEoY6EEMEUOEMISPGsAQMVj4QniQ4IXKQEMXwoMGLoQDDVsQR1NHAS2hQ9XgStYwaUTI24JtBVoBDXtb9MCvVgdJqdcC7QJGJNxz8IQPcQgAE5ArrayIdLi2E1C7mutable7alignedE5ArrayIdLi1E1C7mutable7alignedE5ArrayI10complex128Li1E1C7mutable7alignedE5ArrayI10complex128Li1E1C7mutable7alignedE5ArrayI10complex128Li1E1C7mutable7alignedE5ArrayIdLi1E1C7mutable7alignedE5ArrayI10complex128Li2E1C7mutable7alignedEvN21omitted_28default_3d05_0_29E24omitted_28default_3d0_29N21omitted_28default_3d05_0_29EN21omitted_28default_3d05_0_29E = common local_unnamed_addr global ptr null
@".const.missing Environment: _ZN08NumbaEnv6certus7physics18certus_strat_batch18compute_batch_rmseB2v1B126c8tJTC_2fWQAliW1xhDEoY6EEMEUOEMISPGsAQMVj4QniQ4IXKQEMXwoMGLoQDDVsQR1NHAS2hQ9XgStYwaUTI24JtBVoBDXtb9MCvVgdJqdcC7QJGJNxz8IQPcQgAE5ArrayIdLi2E1C7mutable7alignedE5ArrayIdLi1E1C7mutable7alignedE5ArrayI10complex128Li1E1C7mutable7alignedE5ArrayI10complex128Li1E1C7mutable7alignedE5ArrayI10complex128Li1E1C7mutable7alignedE5ArrayIdLi1E1C7mutable7alignedE5ArrayI10complex128Li2E1C7mutable7alignedEvN21omitted_28default_3d05_0_29E24omitted_28default_3d0_29N21omitted_28default_3d05_0_29EN21omitted_28default_3d05_0_29E" = internal constant [606 x i8] c"missing Environment: _ZN08NumbaEnv6certus7physics18certus_strat_batch18compute_batch_rmseB2v1B126c8tJTC_2fWQAliW1xhDEoY6EEMEUOEMISPGsAQMVj4QniQ4IXKQEMXwoMGLoQDDVsQR1NHAS2hQ9XgStYwaUTI24JtBVoBDXtb9MCvVgdJqdcC7QJGJNxz8IQPcQgAE5ArrayIdLi2E1C7mutable7alignedE5ArrayIdLi1E1C7mutable7alignedE5ArrayI10complex128Li1E1C7mutable7alignedE5ArrayI10complex128Li1E1C7mutable7alignedE5ArrayI10complex128Li1E1C7mutable7alignedE5ArrayIdLi1E1C7mutable7alignedE5ArrayI10complex128Li2E1C7mutable7alignedEvN21omitted_28default_3d05_0_29E24omitted_28default_3d0_29N21omitted_28default_3d05_0_29EN21omitted_28default_3d05_0_29E\00"
@".const.can't unbox array from PyObject into native value.  The object maybe of a different type" = internal constant [89 x i8] c"can't unbox array from PyObject into native value.  The object maybe of a different type\00"
@".const.`env.consts` is NULL in `read_const`" = internal constant [37 x i8] c"`env.consts` is NULL in `read_const`\00"
@.const.pickledata.dfbcfdd39fcb26f4d0c680954487b8c0b53bb8a3 = internal constant [32 x i8] c"\80\04\95\15\00\00\00\00\00\00\00\8C\05numpy\94\8C\07ndarray\94\93\94."
@.const.pickledata.dfbcfdd39fcb26f4d0c680954487b8c0b53bb8a3.sha1 = internal constant [20 x i8] c"\DF\BC\FD\D3\9F\CB&\F4\D0\C6\80\95D\87\B8\C0\B5;\B8\A3"
@".const.Error creating Python tuple from runtime exception arguments" = internal constant [61 x i8] c"Error creating Python tuple from runtime exception arguments\00"
@_ZN08NumbaEnv5numba2np8arrayobj11ol_np_empty12_3clocals_3e4implB3v22B74c8tJTIeFIjxB2IKSgI4CrvQCk0Z4yRYcWsCAgXrKFt1X1eogKfVaTWDAYkQ91Dxg0IFZmgA_3dEx18class_28float64_29 = common local_unnamed_addr global ptr null
@.const.pickledata.331b8563bdb9dac81b38422273052c486fc1706b = internal constant [77 x i8] c"\80\04\95B\00\00\00\00\00\00\00\8C\08builtins\94\8C\0AValueError\94\93\94\8C\1Fnegative dimensions not allowed\94\85\94N\87\94."
@.const.pickledata.331b8563bdb9dac81b38422273052c486fc1706b.sha1 = internal constant [20 x i8] c"3\1B\85c\BD\B9\DA\C8\1B8B\22s\05,Ho\C1pk"
@.const.picklebuf.331b8563bdb9dac81b38422273052c486fc1706b = internal constant { ptr, i32, ptr, ptr, i32 } { ptr @.const.pickledata.331b8563bdb9dac81b38422273052c486fc1706b, i32 77, ptr @.const.pickledata.331b8563bdb9dac81b38422273052c486fc1706b.sha1, ptr null, i32 0 }
@.const.pickledata.58e14eccb507b1e0206981740223e685cb8c3c57 = internal constant [137 x i8] c"\80\04\95~\00\00\00\00\00\00\00\8C\08builtins\94\8C\0AValueError\94\93\94\8C[array is too big; `arr.size * arr.dtype.itemsize` is larger than the maximum possible size.\94\85\94N\87\94."
@.const.pickledata.58e14eccb507b1e0206981740223e685cb8c3c57.sha1 = internal constant [20 x i8] c"X\E1N\CC\B5\07\B1\E0 i\81t\02#\E6\85\CB\8C<W"
@.const.picklebuf.58e14eccb507b1e0206981740223e685cb8c3c57 = internal constant { ptr, i32, ptr, ptr, i32 } { ptr @.const.pickledata.58e14eccb507b1e0206981740223e685cb8c3c57, i32 137, ptr @.const.pickledata.58e14eccb507b1e0206981740223e685cb8c3c57.sha1, ptr null, i32 0 }
@.const.pickledata.ba289d81f05c7020f3477c15734804df65abe209 = internal constant [86 x i8] c"\80\04\95K\00\00\00\00\00\00\00\8C\08builtins\94\8C\0BMemoryError\94\93\94\8C'Allocation failed (probably too large).\94\85\94N\87\94."
@.const.pickledata.ba289d81f05c7020f3477c15734804df65abe209.sha1 = internal constant [20 x i8] c"\BA(\9D\81\F0\\p \F3G|\15sH\04\DFe\AB\E2\09"
@.const.picklebuf.ba289d81f05c7020f3477c15734804df65abe209 = internal constant { ptr, i32, ptr, ptr, i32 } { ptr @.const.pickledata.ba289d81f05c7020f3477c15734804df65abe209, i32 86, ptr @.const.pickledata.ba289d81f05c7020f3477c15734804df65abe209.sha1, ptr null, i32 0 }
@_ZN08NumbaEnv13_3cdynamic_3e35__numba_parfor_gufunc_0x24b561942f0B3v23B138c8tJTC_2fWQAliW1xhDEoY6EEMEUOEMISPGsAQMVj4QniQ4IXKQEMXwoMGLoQDDVsQR1NHAS2hQ9XgStYwaUTI24JtBVoBDXtb9MCvVgdJqdcC7YLGAMy5RSVwr8KzAcRZAA_3d_3dE5ArrayIyLi1E1C7mutable7alignedE5ArrayIdLi1E1C7mutable7alignedE5ArrayIdLi1E1C7mutable7alignedE = common local_unnamed_addr global ptr null
@".const.Error creating Python tuple from runtime exception arguments.9" = internal constant [61 x i8] c"Error creating Python tuple from runtime exception arguments\00"
@".const.unknown error when calling native function.10" = internal constant [43 x i8] c"unknown error when calling native function\00"
@.const.pickledata.331b8563bdb9dac81b38422273052c486fc1706b.16 = internal constant [77 x i8] c"\80\04\95B\00\00\00\00\00\00\00\8C\08builtins\94\8C\0AValueError\94\93\94\8C\1Fnegative dimensions not allowed\94\85\94N\87\94."
@.const.pickledata.331b8563bdb9dac81b38422273052c486fc1706b.sha1.17 = internal constant [20 x i8] c"3\1B\85c\BD\B9\DA\C8\1B8B\22s\05,Ho\C1pk"
@.const.picklebuf.331b8563bdb9dac81b38422273052c486fc1706b.15 = internal constant { ptr, i32, ptr, ptr, i32 } { ptr @.const.pickledata.331b8563bdb9dac81b38422273052c486fc1706b.16, i32 77, ptr @.const.pickledata.331b8563bdb9dac81b38422273052c486fc1706b.sha1.17, ptr null, i32 0 }
@.const.pickledata.58e14eccb507b1e0206981740223e685cb8c3c57.18 = internal constant [137 x i8] c"\80\04\95~\00\00\00\00\00\00\00\8C\08builtins\94\8C\0AValueError\94\93\94\8C[array is too big; `arr.size * arr.dtype.itemsize` is larger than the maximum possible size.\94\85\94N\87\94."
@.const.pickledata.58e14eccb507b1e0206981740223e685cb8c3c57.sha1.19 = internal constant [20 x i8] c"X\E1N\CC\B5\07\B1\E0 i\81t\02#\E6\85\CB\8C<W"
@.const.picklebuf.58e14eccb507b1e0206981740223e685cb8c3c57.14 = internal constant { ptr, i32, ptr, ptr, i32 } { ptr @.const.pickledata.58e14eccb507b1e0206981740223e685cb8c3c57.18, i32 137, ptr @.const.pickledata.58e14eccb507b1e0206981740223e685cb8c3c57.sha1.19, ptr null, i32 0 }
@.const.pickledata.ba289d81f05c7020f3477c15734804df65abe209.20 = internal constant [86 x i8] c"\80\04\95K\00\00\00\00\00\00\00\8C\08builtins\94\8C\0BMemoryError\94\93\94\8C'Allocation failed (probably too large).\94\85\94N\87\94."
@.const.pickledata.ba289d81f05c7020f3477c15734804df65abe209.sha1.21 = internal constant [20 x i8] c"\BA(\9D\81\F0\\p \F3G|\15sH\04\DFe\AB\E2\09"
@.const.picklebuf.ba289d81f05c7020f3477c15734804df65abe209.13 = internal constant { ptr, i32, ptr, ptr, i32 } { ptr @.const.pickledata.ba289d81f05c7020f3477c15734804df65abe209.20, i32 86, ptr @.const.pickledata.ba289d81f05c7020f3477c15734804df65abe209.sha1.21, ptr null, i32 0 }
@.const.pickledata.b6e474b50ffce3a1cb8e957957228030e14ea2dc = internal constant [200 x i8] c"\80\04\95\BD\00\00\00\00\00\00\00\8C\08builtins\94\8C\11ZeroDivisionError\94\93\94\8C\18complex division by zero\94\85\94\8C\0Bcomplex_div\94\8CfC:\\Users\\Lemarchand\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\numba\\cpython\\numbers.py\94Mw\04\87\94\87\94."
@.const.pickledata.b6e474b50ffce3a1cb8e957957228030e14ea2dc.sha1 = internal constant [20 x i8] c"\B6\E4t\B5\0F\FC\E3\A1\CB\8E\95yW\22\800\E1N\A2\DC"
@.const.picklebuf.b6e474b50ffce3a1cb8e957957228030e14ea2dc = internal constant { ptr, i32, ptr, ptr, i32 } { ptr @.const.pickledata.b6e474b50ffce3a1cb8e957957228030e14ea2dc, i32 200, ptr @.const.pickledata.b6e474b50ffce3a1cb8e957957228030e14ea2dc.sha1, ptr null, i32 0 }
@.const.pickledata.b28008a0f88bad5ff0f0243e84dab90cab19b366 = internal constant [69 x i8] c"\80\04\95:\00\00\00\00\00\00\00\8C\08builtins\94\8C\11ZeroDivisionError\94\93\94\8C\10division by zero\94\85\94N\87\94."
@.const.pickledata.b28008a0f88bad5ff0f0243e84dab90cab19b366.sha1 = internal constant [20 x i8] c"\B2\80\08\A0\F8\8B\AD_\F0\F0$>\84\DA\B9\0C\AB\19\B3f"
@.const.picklebuf.b28008a0f88bad5ff0f0243e84dab90cab19b366 = internal constant { ptr, i32, ptr, ptr, i32 } { ptr @.const.pickledata.b28008a0f88bad5ff0f0243e84dab90cab19b366, i32 69, ptr @.const.pickledata.b28008a0f88bad5ff0f0243e84dab90cab19b366.sha1, ptr null, i32 0 }
@.const.pickledata.b6e474b50ffce3a1cb8e957957228030e14ea2dc.17 = internal constant [200 x i8] c"\80\04\95\BD\00\00\00\00\00\00\00\8C\08builtins\94\8C\11ZeroDivisionError\94\93\94\8C\18complex division by zero\94\85\94\8C\0Bcomplex_div\94\8CfC:\\Users\\Lemarchand\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\numba\\cpython\\numbers.py\94Mw\04\87\94\87\94."
@.const.pickledata.b6e474b50ffce3a1cb8e957957228030e14ea2dc.sha1.18 = internal constant [20 x i8] c"\B6\E4t\B5\0F\FC\E3\A1\CB\8E\95yW\22\800\E1N\A2\DC"
@.const.picklebuf.b6e474b50ffce3a1cb8e957957228030e14ea2dc.16 = internal constant { ptr, i32, ptr, ptr, i32 } { ptr @.const.pickledata.b6e474b50ffce3a1cb8e957957228030e14ea2dc.17, i32 200, ptr @.const.pickledata.b6e474b50ffce3a1cb8e957957228030e14ea2dc.sha1.18, ptr null, i32 0 }
@.const.pickledata.b28008a0f88bad5ff0f0243e84dab90cab19b366.19 = internal constant [69 x i8] c"\80\04\95:\00\00\00\00\00\00\00\8C\08builtins\94\8C\11ZeroDivisionError\94\93\94\8C\10division by zero\94\85\94N\87\94."
@.const.pickledata.b28008a0f88bad5ff0f0243e84dab90cab19b366.sha1.20 = internal constant [20 x i8] c"\B2\80\08\A0\F8\8B\AD_\F0\F0$>\84\DA\B9\0C\AB\19\B3f"
@.const.picklebuf.b28008a0f88bad5ff0f0243e84dab90cab19b366.15 = internal constant { ptr, i32, ptr, ptr, i32 } { ptr @.const.pickledata.b28008a0f88bad5ff0f0243e84dab90cab19b366.19, i32 69, ptr @.const.pickledata.b28008a0f88bad5ff0f0243e84dab90cab19b366.sha1.20, ptr null, i32 0 }
@_ZN08NumbaEnv13_3cdynamic_3e35__numba_parfor_gufunc_0x24b56214910B3v24B126c8tJTC_2fWQAliW1xhDEoY6EEMEUOEMISPGsAQMVj4QniQ4IXKQEMXwoMGLoQDDVsQR1NHAS2hQ9XgStYwaUTI24JtBVoBDXtb9MCvVgdJqdcC7QJGJNxz8IQPcQgAE5ArrayIyLi1E1C7mutable7alignedEb5ArrayIdLi1E1C7mutable7alignedEddd23Literal_5bint_5d_280_295ArrayIdLi1E1C7mutable7alignedE5ArrayI10complex128Li1E1C7mutable7alignedEx5ArrayI10complex128Li2E1C7mutable7alignedE5ArrayIdLi2E1C7mutable7alignedE5ArrayIdLi1E1C7mutable7alignedEx5ArrayIdLi1E1C7mutable7alignedE = common local_unnamed_addr global ptr null
@PyExc_StopIteration = external global i8
@PyExc_SystemError = external global i8
@_ZN08NumbaEnv5numba2np8arrayobj11ol_np_empty12_3clocals_3e4implB2v9B74c8tJTIeFIjxB2IKSgI4CrvQCk0Z4yRYcWsCAgXrKFt1X1eogKfVaTWDAYkQ91Dxg0IFZmgA_3dEx21class_28complex128_29 = common local_unnamed_addr global ptr null
@_ZN08NumbaEnv5numba2np8arrayobj15_call_allocatorB2v3B42c8tJTC_2fWQA93W1AaAIYBPIqRBFCjDSZRVAJmaQIAEN29typeref_5b_3cclass_20_27numba4core5types8npytypes14Array_27_3e_5dExj = common local_unnamed_addr global ptr null
@_ZN08NumbaEnv5numba2np8arrayobj18_ol_array_allocate12_3clocals_3e4implB2v4B42c8tJTIeFIjxB2IKSgI4CrvQClcaMQ5hEEUSJJgA_3dEN29typeref_5b_3cclass_20_27numba4core5types8npytypes14Array_27_3e_5dExj = common local_unnamed_addr global ptr null
@_ZN08NumbaEnv6certus7physics17certus_strat_math20_seeded_noise_sampleB3v25B76c8tJTIeFIjxB2IKSgI4CrvQCk0Z4yRYcWsCAgXrKFt1X1eogKfVaTWDAFsEMQEpRYBFNAA_3d_3dE23Literal_5bint_5d_280_2923Literal_5bint_5d_280_29y23Literal_5bint_5d_280_2927Literal_5bbool_5d_28True_29 = common local_unnamed_addr global ptr null
@_ZN08NumbaEnv6certus7physics17certus_strat_math20_seeded_noise_sampleB3v26B76c8tJTIeFIjxB2IKSgI4CrvQCk0Z4yRYcWsCAgXrKFt1X1eogKfVaTWDAFsEMQEpRYBFNAA_3d_3dE23Literal_5bint_5d_280_2923Literal_5bint_5d_280_29y23Literal_5bint_5d_281_2927Literal_5bbool_5d_28True_29 = common local_unnamed_addr global ptr null
@_ZN08NumbaEnv6certus7physics17certus_strat_math20_seeded_noise_sampleB3v27B76c8tJTIeFIjxB2IKSgI4CrvQCk0Z4yRYcWsCAgXrKFt1X1eogKfVaTWDAFsEMQEpRYBFNAA_3d_3dE23Literal_5bint_5d_280_2923Literal_5bint_5d_281_29y23Literal_5bint_5d_280_2927Literal_5bbool_5d_28True_29 = common local_unnamed_addr global ptr null
@_ZN08NumbaEnv6certus7physics17certus_strat_math20_seeded_noise_sampleB3v28B76c8tJTIeFIjxB2IKSgI4CrvQCk0Z4yRYcWsCAgXrKFt1X1eogKfVaTWDAFsEMQEpRYBFNAA_3d_3dE23Literal_5bint_5d_280_2923Literal_5bint_5d_281_29y23Literal_5bint_5d_281_2927Literal_5bbool_5d_28True_29 = common local_unnamed_addr global ptr null
@_ZN08NumbaEnv6certus7physics17certus_tmm_matrix33compute_TMM_single_point_k0_exactB3v10B76c8tJTIeFIjxB2IKSgI4CrvQCk0Z4yRYcWsCAgXrKFt1X1eogKfVaTWDAFsEMQEpRYBFNAA_3d_3dEd5ArrayIdLi1E1C7mutable7alignedE5ArrayI10complex128Li1E1C7mutable7alignedE10complex128 = common local_unnamed_addr global ptr null
@_ZN08NumbaEnv5numba2np4math9cmathimpl8cos_impl12_3clocals_3e8cos_implB3v18B42c8tJTC_2fWQA93W1AaAIYBPIqRBFCjDSZRVAJmaQIAE10complex128 = common local_unnamed_addr global ptr null
@_ZN08NumbaEnv5numba7cpython9cmathimpl15impl_cmath_cosh12_3clocals_3e9cosh_implB3v19B42c8tJTIeFIjxB2IKSgI4CrvQClcaMQ5hEEUSJJgA_3dE10complex128 = common local_unnamed_addr global ptr null
@_ZN08NumbaEnv5numba2np4math9cmathimpl8sin_impl12_3clocals_3e8sin_implB3v20B42c8tJTC_2fWQA93W1AaAIYBPIqRBFCjDSZRVAJmaQIAE10complex128 = common local_unnamed_addr global ptr null
@_ZN08NumbaEnv5numba7cpython9cmathimpl15impl_cmath_sinh12_3clocals_3e9sinh_implB3v21B42c8tJTIeFIjxB2IKSgI4CrvQClcaMQ5hEEUSJJgA_3dE10complex128 = common local_unnamed_addr global ptr null
@_ZN08NumbaEnv6certus7physics14certus_opt_tmm22compute_RT_from_matrixB3v11B76c8tJTIeFIjxB2IKSgI4CrvQCk0Z4yRYcWsCAgXrKFt1X1eogKfVaTWDAFsEMQEpRYBFNAA_3d_3dE10complex12810complex12810complex12810complex12810complex12810complex128 = common local_unnamed_addr global ptr null
@PyExc_TypeError = external global i8
@PyExc_RuntimeError = external global i8
@_ZN08NumbaEnv5numba7cpython7numbers16complex_mul_impl12_3clocals_3e11complex_mulB3v13B42c8tJTC_2fWQA93W1AaAIYBPIqRBFCjDSZRVAJmaQIAE10complex12810complex128 = common local_unnamed_addr global ptr null
@_ZN08NumbaEnv5numba7cpython7numbers16complex_abs_impl12_3clocals_3e11complex_absB3v14B42c8tJTC_2fWQA93W1AaAIYBPIqRBFCjDSZRVAJmaQIAE10complex128 = common local_unnamed_addr global ptr null
@_ZN08NumbaEnv5numba7cpython8mathimpl16hypot_float_impl12_3clocals_3e10hypot_implB3v15B42c8tJTC_2fWQA93W1AaAIYBPIqRBFCjDSZRVAJmaQIAEdd = common local_unnamed_addr global ptr null
@_ZN08NumbaEnv5numba7cpython7numbers16complex_div_impl12_3clocals_3e11complex_divB3v16B42c8tJTC_2fWQA93W1AaAIYBPIqRBFCjDSZRVAJmaQIAE10complex12810complex128 = common local_unnamed_addr global ptr null
@_ZN08NumbaEnv5numba7cpython7numbers14int_power_impl12_3clocals_3e9int_powerB3v17B42c8tJTC_2fWQA93W1AaAIYBPIqRBFCjDSZRVAJmaQIAEdx = common local_unnamed_addr global ptr null
@_ZN08NumbaEnv5numba7cpython8builtins6ol_max12_3clocals_3e4implB3v12B74c8tJTIeFIjxB2IKSgI4CrvQCk0Z4yRYcWsCAgXrKFt1X1eogKfVaTWDAYkQ91Dxg0IFZmgA_3dE15StarArgUniTupleIdLi2EE = common local_unnamed_addr global ptr null

define range(i32 0, 2) i32 @_ZN6certus7physics18certus_strat_batch18compute_batch_rmseB2v1B126c8tJTC_2fWQAliW1xhDEoY6EEMEUOEMISPGsAQMVj4QniQ4IXKQEMXwoMGLoQDDVsQR1NHAS2hQ9XgStYwaUTI24JtBVoBDXtb9MCvVgdJqdcC7QJGJNxz8IQPcQgAE5ArrayIdLi2E1C7mutable7alignedE5ArrayIdLi1E1C7mutable7alignedE5ArrayI10complex128Li1E1C7mutable7alignedE5ArrayI10complex128Li1E1C7mutable7alignedE5ArrayI10complex128Li1E1C7mutable7alignedE5ArrayIdLi1E1C7mutable7alignedE5ArrayI10complex128Li2E1C7mutable7alignedEvN21omitted_28default_3d05_0_29E24omitted_28default_3d0_29N21omitted_28default_3d05_0_29EN21omitted_28default_3d05_0_29E(ptr noalias writeonly captures(none) %retptr, ptr noalias writeonly captures(none) %excinfo, ptr %arg.sim_thick_batch.0, ptr readnone captures(none) %arg.sim_thick_batch.1, i64 %arg.sim_thick_batch.2, i64 %arg.sim_thick_batch.3, ptr %arg.sim_thick_batch.4, i64 %arg.sim_thick_batch.5.0, i64 %arg.sim_thick_batch.5.1, i64 %arg.sim_thick_batch.6.0, i64 %arg.sim_thick_batch.6.1, ptr %arg.wls.0, ptr readnone captures(none) %arg.wls.1, i64 %arg.wls.2, i64 %arg.wls.3, ptr %arg.wls.4, i64 %arg.wls.5.0, i64 %arg.wls.6.0, ptr readnone captures(none) %arg.nH_arr.0, ptr readnone captures(none) %arg.nH_arr.1, i64 %arg.nH_arr.2, i64 %arg.nH_arr.3, ptr readnone captures(none) %arg.nH_arr.4, i64 %arg.nH_arr.5.0, i64 %arg.nH_arr.6.0, ptr readnone captures(none) %arg.nL_arr.0, ptr readnone captures(none) %arg.nL_arr.1, i64 %arg.nL_arr.2, i64 %arg.nL_arr.3, ptr readnone captures(none) %arg.nL_arr.4, i64 %arg.nL_arr.5.0, i64 %arg.nL_arr.6.0, ptr %arg.nSub_arr.0, ptr readnone captures(none) %arg.nSub_arr.1, i64 %arg.nSub_arr.2, i64 %arg.nSub_arr.3, ptr %arg.nSub_arr.4, i64 %arg.nSub_arr.5.0, i64 %arg.nSub_arr.6.0, ptr %arg.T_target.0, ptr readnone captures(none) %arg.T_target.1, i64 %arg.T_target.2, i64 %arg.T_target.3, ptr %arg.T_target.4, i64 %arg.T_target.5.0, i64 %arg.T_target.6.0, ptr %arg.n_layers_flattened.0, ptr readnone captures(none) %arg.n_layers_flattened.1, i64 %arg.n_layers_flattened.2, i64 %arg.n_layers_flattened.3, ptr %arg.n_layers_flattened.4, i64 %arg.n_layers_flattened.5.0, i64 %arg.n_layers_flattened.5.1, i64 %arg.n_layers_flattened.6.0, i64 %arg.n_layers_flattened.6.1, ptr readnone captures(none) %arg.weights) local_unnamed_addr {
B0:
  %.7.i23 = alloca i32, align 4
  %.7.i = alloca i32, align 4
  %dim_starts = alloca i64, align 8
  store i64 0, ptr %dim_starts, align 8
  %dim_stops = alloca i64, align 8
  store i64 0, ptr %dim_stops, align 8
  %pargs506 = alloca [3 x ptr], align 8
  store ptr null, ptr %pargs506, align 8
  %pshape507 = alloca [3 x i64], align 8
  store i64 0, ptr %pshape507, align 8
  %psteps508 = alloca [6 x i64], align 8
  store i64 0, ptr %psteps508, align 8
  %dim_starts.1 = alloca i64, align 8
  store i64 0, ptr %dim_starts.1, align 8
  %dim_stops.1 = alloca i64, align 8
  store i64 0, ptr %dim_stops.1, align 8
  %pargs.1509 = alloca [15 x ptr], align 8
  store ptr null, ptr %pargs.1509, align 8
  %.512 = alloca i1, align 1
  store i1 false, ptr %.512, align 1
  %.530 = alloca double, align 8
  store double 0.000000e+00, ptr %.530, align 8
  %.536 = alloca double, align 8
  store double 0.000000e+00, ptr %.536, align 8
  %.542 = alloca double, align 8
  store double 0.000000e+00, ptr %.542, align 8
  %.548 = alloca i64, align 8
  store i64 0, ptr %.548, align 8
  %.578 = alloca i64, align 8
  store i64 0, ptr %.578, align 8
  %.622 = alloca i64, align 8
  store i64 0, ptr %.622, align 8
  %pshape.1510 = alloca [9 x i64], align 8
  store i64 0, ptr %pshape.1510, align 8
  %psteps.1511 = alloca [25 x i64], align 8
  store i64 0, ptr %psteps.1511, align 8
  tail call void @NRT_incref(ptr %arg.sim_thick_batch.0)
  tail call void @NRT_incref(ptr %arg.wls.0)
  tail call void @NRT_incref(ptr %arg.nSub_arr.0)
  tail call void @NRT_incref(ptr %arg.T_target.0)
  tail call void @NRT_incref(ptr %arg.n_layers_flattened.0)
  %.15.i = icmp slt i64 %arg.sim_thick_batch.5.0, 0
  br i1 %.15.i, label %B0.if.if, label %B0.endif.endif.i, !prof !0

B0.endif.endif.i:                                 ; preds = %B0
  %const = bitcast i64 1152921504606846975 to i64
  %.31.i = icmp samesign ugt i64 %arg.sim_thick_batch.5.0, %const
  br i1 %.31.i, label %B0.if.if, label %B0.endif.endif.endif.i, !prof !0

B0.endif.endif.endif.i:                           ; preds = %B0.endif.endif.i
  %.30.i = shl nuw nsw i64 %arg.sim_thick_batch.5.0, 3
  %.7.i.i.i = tail call ptr @NRT_MemInfo_alloc_aligned(i64 %.30.i, i32 32), !noalias !1
  %.8.i.i.i = icmp eq ptr %.7.i.i.i, null
  br i1 %.8.i.i.i, label %B0.if.if, label %B0.endif, !prof !0

B236:                                             ; preds = %B0.endif.endif
  %.356 = call i64 @get_sched_size(i64 %.345, i64 1, ptr nonnull %dim_starts, ptr nonnull %dim_stops)
  call void @set_parallel_chunksize(i64 0)
  %.358 = shl i64 %.356, 1
  %.359 = call ptr @allocate_sched(i64 %.358)
  %.364 = call ptr @do_scheduling_unsigned(i64 1, ptr nonnull %dim_starts, ptr nonnull %dim_stops, i64 %.356, ptr %.359, i64 0)
  store ptr %.359, ptr %pargs506, align 8
  %.371 = getelementptr inbounds nuw i8, ptr %pargs506, i64 8
  store ptr %arg.wls.4, ptr %.371, align 8
  %.383 = getelementptr inbounds nuw i8, ptr %pargs506, i64 16
  store ptr %.6.i.i11, ptr %.383, align 8
  store i64 %.356, ptr %pshape507, align 8
  %.415 = getelementptr inbounds nuw i8, ptr %pshape507, i64 8
  store i64 2, ptr %.415, align 8
  %.417 = getelementptr inbounds nuw i8, ptr %pshape507, i64 16
  store i64 %arg.wls.5.0, ptr %.417, align 8
  store i64 16, ptr %psteps508, align 8
  %.421 = getelementptr inbounds nuw i8, ptr %psteps508, i64 8
  %.425 = getelementptr inbounds nuw i8, ptr %psteps508, i64 24
  call void @llvm.memset.p0.i64(ptr noundef nonnull align 8 dereferenceable(16) %.421, i8 0, i64 16, i1 false)
  store i64 8, ptr %.425, align 8
  %.427 = getelementptr inbounds nuw i8, ptr %psteps508, i64 32
  store i64 %arg.wls.6.0, ptr %.427, align 8
  %.429 = getelementptr inbounds nuw i8, ptr %psteps508, i64 40
  store i64 8, ptr %.429, align 8
  call void @llvm.lifetime.start.p0(ptr nonnull %.7.i23)
  store i32 0, ptr %.7.i23, align 4
  call void @numba_gil_ensure(ptr nonnull %.7.i23)
  %.10.i = call ptr @PyEval_SaveThread()
  %.11.i = call i64 @get_num_threads()
  call void @numba_parallel_for(ptr nonnull @__gufunc__._ZN13_3cdynamic_3e35__numba_parfor_gufunc_0x24b561942f0B3v23B138c8tJTC_2fWQAliW1xhDEoY6EEMEUOEMISPGsAQMVj4QniQ4IXKQEMXwoMGLoQDDVsQR1NHAS2hQ9XgStYwaUTI24JtBVoBDXtb9MCvVgdJqdcC7YLGAMy5RSVwr8KzAcRZAA_3d_3dE5ArrayIyLi1E1C7mutable7alignedE5ArrayIdLi1E1C7mutable7alignedE5ArrayIdLi1E1C7mutable7alignedE, ptr nonnull %pargs506, ptr nonnull %pshape507, ptr nonnull %psteps508, ptr null, i64 2, i64 3, i64 %.11.i)
  call void @PyEval_RestoreThread(ptr %.10.i)
  call void @numba_gil_release(ptr nonnull %.7.i23)
  call void @llvm.lifetime.end.p0(ptr nonnull %.7.i23)
  call void @set_parallel_chunksize(i64 %.346)
  call void @deallocate_sched(ptr %.359)
  %.468 = add nsw i64 %arg.sim_thick_batch.5.0, -1
  store i64 0, ptr %dim_starts.1, align 8
  store i64 %.468, ptr %dim_stops.1, align 8
  %.473 = call i64 @get_num_threads()
  %.474 = call i64 @get_parallel_chunksize()
  %.475 = icmp slt i64 %.473, 1
  br i1 %.475, label %B236.if, label %B236.endif, !prof !0

B0.endif:                                         ; preds = %B0.endif.endif.endif.i
  %.5.i.i = getelementptr i8, ptr %.7.i.i.i, i64 24
  %.6.i.i = load ptr, ptr %.5.i.i, align 8, !noalias !11
  %.15.i2 = icmp slt i64 %arg.wls.5.0, 0
  br i1 %.15.i2, label %B0.endif.if.if, label %B0.endif.endif.i3, !prof !0

B0.endif.endif.i3:                                ; preds = %B0.endif
  %.31.i4 = icmp samesign ugt i64 %arg.wls.5.0, %const
  br i1 %.31.i4, label %B0.endif.if.if, label %B0.endif.endif.endif.i5, !prof !0

B0.endif.endif.endif.i5:                          ; preds = %B0.endif.endif.i3
  %.30.i6 = shl nuw nsw i64 %arg.wls.5.0, 3
  %.7.i.i.i7 = tail call ptr @NRT_MemInfo_alloc_aligned(i64 %.30.i6, i32 32), !noalias !12
  %.8.i.i.i8 = icmp eq ptr %.7.i.i.i7, null
  br i1 %.8.i.i.i8, label %B0.endif.if.if, label %B0.endif.endif, !prof !0

common.ret:                                       ; preds = %B236.endif, %B236.if, %B0.endif.endif.if, %B0.endif.if.if, %B0.if.if
  %common.ret.op = phi i32 [ 1, %B0.if.if ], [ 1, %B0.endif.if.if ], [ 1, %B0.endif.endif.if ], [ 1, %B236.if ], [ 0, %B236.endif ]
  ret i32 %common.ret.op

B0.if.if:                                         ; preds = %B0.endif.endif.i, %B0, %B0.endif.endif.endif.i
  %excinfo.1.0.ph = phi ptr [ @.const.picklebuf.ba289d81f05c7020f3477c15734804df65abe209, %B0.endif.endif.endif.i ], [ @.const.picklebuf.58e14eccb507b1e0206981740223e685cb8c3c57, %B0.endif.endif.i ], [ @.const.picklebuf.331b8563bdb9dac81b38422273052c486fc1706b, %B0 ]
  store ptr %excinfo.1.0.ph, ptr %excinfo, align 8
  br label %common.ret

B0.endif.endif:                                   ; preds = %B0.endif.endif.endif.i5
  %.5.i.i10 = getelementptr i8, ptr %.7.i.i.i7, i64 24
  %.6.i.i11 = load ptr, ptr %.5.i.i10, align 8, !noalias !22
  %.340 = add nsw i64 %arg.wls.5.0, -1
  store i64 0, ptr %dim_starts, align 8
  store i64 %.340, ptr %dim_stops, align 8
  %.345 = tail call i64 @get_num_threads()
  %.346 = tail call i64 @get_parallel_chunksize()
  %.347 = icmp slt i64 %.345, 1
  br i1 %.347, label %B0.endif.endif.if, label %B236, !prof !0

B0.endif.if.if:                                   ; preds = %B0.endif.endif.i3, %B0.endif, %B0.endif.endif.endif.i5
  %excinfo.2.0.ph = phi ptr [ @.const.picklebuf.ba289d81f05c7020f3477c15734804df65abe209, %B0.endif.endif.endif.i5 ], [ @.const.picklebuf.58e14eccb507b1e0206981740223e685cb8c3c57, %B0.endif.endif.i3 ], [ @.const.picklebuf.331b8563bdb9dac81b38422273052c486fc1706b, %B0.endif ]
  store ptr %excinfo.2.0.ph, ptr %excinfo, align 8
  br label %common.ret

B0.endif.endif.if:                                ; preds = %B0.endif.endif
  %.350 = tail call i32 (ptr, ...) @printf(ptr noundef nonnull dereferenceable(1) @printf_format, i64 %.345)
  store ptr @.const.picklebuf.9d8bd6d541b3e336fd7917994940781bc68a3a8a, ptr %excinfo, align 8, !numba_exception_output !23
  br label %common.ret

B236.if:                                          ; preds = %B236
  %.478 = call i32 (ptr, ...) @printf(ptr noundef nonnull dereferenceable(1) @printf_format.1, i64 %.473)
  store ptr @.const.picklebuf.9d8bd6d541b3e336fd7917994940781bc68a3a8a, ptr %excinfo, align 8, !numba_exception_output !23
  br label %common.ret

B236.endif:                                       ; preds = %B236
  %.484 = call i64 @get_sched_size(i64 %.473, i64 1, ptr nonnull %dim_starts.1, ptr nonnull %dim_stops.1)
  call void @set_parallel_chunksize(i64 0)
  %.486 = shl i64 %.484, 1
  %.487 = call ptr @allocate_sched(i64 %.486)
  %.492 = call ptr @do_scheduling_unsigned(i64 1, ptr nonnull %dim_starts.1, ptr nonnull %dim_stops.1, i64 %.484, ptr %.487, i64 0)
  store ptr %.487, ptr %pargs.1509, align 8
  %.511 = getelementptr inbounds nuw i8, ptr %pargs.1509, i64 8
  store i1 false, ptr %.512, align 1
  store ptr %.512, ptr %.511, align 8
  %.517 = getelementptr inbounds nuw i8, ptr %pargs.1509, i64 16
  store ptr %arg.T_target.4, ptr %.517, align 8
  %.529 = getelementptr inbounds nuw i8, ptr %pargs.1509, i64 24
  store double 0.000000e+00, ptr %.530, align 8
  store ptr %.530, ptr %.529, align 8
  %.535 = getelementptr inbounds nuw i8, ptr %pargs.1509, i64 32
  store double 0.000000e+00, ptr %.536, align 8
  store ptr %.536, ptr %.535, align 8
  %.541 = getelementptr inbounds nuw i8, ptr %pargs.1509, i64 40
  store double 0.000000e+00, ptr %.542, align 8
  store ptr %.542, ptr %.541, align 8
  %.547 = getelementptr inbounds nuw i8, ptr %pargs.1509, i64 48
  store i64 0, ptr %.548, align 8
  store ptr %.548, ptr %.547, align 8
  %.553 = getelementptr inbounds nuw i8, ptr %pargs.1509, i64 56
  store ptr %.6.i.i11, ptr %.553, align 8
  %.565 = getelementptr inbounds nuw i8, ptr %pargs.1509, i64 64
  store ptr %arg.nSub_arr.4, ptr %.565, align 8
  %.577 = getelementptr inbounds nuw i8, ptr %pargs.1509, i64 72
  store i64 %arg.sim_thick_batch.5.1, ptr %.578, align 8
  store ptr %.578, ptr %.577, align 8
  %.583 = getelementptr inbounds nuw i8, ptr %pargs.1509, i64 80
  store ptr %arg.n_layers_flattened.4, ptr %.583, align 8
  %.596 = getelementptr inbounds nuw i8, ptr %pargs.1509, i64 88
  store ptr %arg.sim_thick_batch.4, ptr %.596, align 8
  %.609 = getelementptr inbounds nuw i8, ptr %pargs.1509, i64 96
  store ptr %arg.wls.4, ptr %.609, align 8
  %.621 = getelementptr inbounds nuw i8, ptr %pargs.1509, i64 104
  store i64 %arg.wls.5.0, ptr %.622, align 8
  store ptr %.622, ptr %.621, align 8
  %.627 = getelementptr inbounds nuw i8, ptr %pargs.1509, i64 112
  store ptr %.6.i.i, ptr %.627, align 8
  store i64 %.484, ptr %pshape.1510, align 8
  %.738 = getelementptr inbounds nuw i8, ptr %pshape.1510, i64 8
  store i64 2, ptr %.738, align 8
  %.740 = getelementptr inbounds nuw i8, ptr %pshape.1510, i64 16
  store i64 %arg.T_target.5.0, ptr %.740, align 8
  %.742 = getelementptr inbounds nuw i8, ptr %pshape.1510, i64 24
  store i64 %arg.wls.5.0, ptr %.742, align 8
  %.744 = getelementptr inbounds nuw i8, ptr %pshape.1510, i64 32
  store i64 %arg.nSub_arr.5.0, ptr %.744, align 8
  %.746 = getelementptr inbounds nuw i8, ptr %pshape.1510, i64 40
  store i64 %arg.n_layers_flattened.5.0, ptr %.746, align 8
  %.748 = getelementptr inbounds nuw i8, ptr %pshape.1510, i64 48
  store i64 %arg.n_layers_flattened.5.1, ptr %.748, align 8
  %.750 = getelementptr inbounds nuw i8, ptr %pshape.1510, i64 56
  store i64 %arg.sim_thick_batch.5.0, ptr %.750, align 8
  %.752 = getelementptr inbounds nuw i8, ptr %pshape.1510, i64 64
  store i64 %arg.sim_thick_batch.5.1, ptr %.752, align 8
  store i64 16, ptr %psteps.1511, align 8
  %.756 = getelementptr inbounds nuw i8, ptr %psteps.1511, i64 8
  %.784 = getelementptr inbounds nuw i8, ptr %psteps.1511, i64 120
  call void @llvm.memset.p0.i64(ptr noundef nonnull align 8 dereferenceable(112) %.756, i8 0, i64 112, i1 false)
  store i64 8, ptr %.784, align 8
  %.786 = getelementptr inbounds nuw i8, ptr %psteps.1511, i64 128
  store i64 %arg.T_target.6.0, ptr %.786, align 8
  %.788 = getelementptr inbounds nuw i8, ptr %psteps.1511, i64 136
  store i64 8, ptr %.788, align 8
  %.790 = getelementptr inbounds nuw i8, ptr %psteps.1511, i64 144
  store i64 %arg.nSub_arr.6.0, ptr %.790, align 8
  %.792 = getelementptr inbounds nuw i8, ptr %psteps.1511, i64 152
  store i64 %arg.n_layers_flattened.6.0, ptr %.792, align 8
  %.794 = getelementptr inbounds nuw i8, ptr %psteps.1511, i64 160
  store i64 %arg.n_layers_flattened.6.1, ptr %.794, align 8
  %.796 = getelementptr inbounds nuw i8, ptr %psteps.1511, i64 168
  store i64 %arg.sim_thick_batch.6.0, ptr %.796, align 8
  %.798 = getelementptr inbounds nuw i8, ptr %psteps.1511, i64 176
  store i64 %arg.sim_thick_batch.6.1, ptr %.798, align 8
  %.800 = getelementptr inbounds nuw i8, ptr %psteps.1511, i64 184
  store i64 %arg.wls.6.0, ptr %.800, align 8
  %.802 = getelementptr inbounds nuw i8, ptr %psteps.1511, i64 192
  store i64 8, ptr %.802, align 8
  call void @llvm.lifetime.start.p0(ptr nonnull %.7.i23)
  store i32 0, ptr %.7.i23, align 4
  call void @numba_gil_ensure(ptr nonnull %.7.i23)
  %.10.i24 = call ptr @PyEval_SaveThread()
  %.11.i25 = call i64 @get_num_threads()
  call void @numba_parallel_for(ptr nonnull @__gufunc__._ZN13_3cdynamic_3e35__numba_parfor_gufunc_0x24b56214910B3v24B126c8tJTC_2fWQAliW1xhDEoY6EEMEUOEMISPGsAQMVj4QniQ4IXKQEMXwoMGLoQDDVsQR1NHAS2hQ9XgStYwaUTI24JtBVoBDXtb9MCvVgdJqdcC7QJGJNxz8IQPcQgAE5ArrayIyLi1E1C7mutable7alignedEb5ArrayIdLi1E1C7mutable7alignedEddd23Literal_5bint_5d_280_295ArrayIdLi1E1C7mutable7alignedE5ArrayI10complex128Li1E1C7mutable7alignedEx5ArrayI10complex128Li2E1C7mutable7alignedE5ArrayIdLi2E1C7mutable7alignedE5ArrayIdLi1E1C7mutable7alignedEx5ArrayIdLi1E1C7mutable7alignedE, ptr nonnull %pargs.1509, ptr nonnull %pshape.1510, ptr nonnull %psteps.1511, ptr null, i64 8, i64 15, i64 %.11.i25)
  call void @PyEval_RestoreThread(ptr %.10.i24)
  call void @numba_gil_release(ptr nonnull %.7.i23)
  call void @llvm.lifetime.end.p0(ptr nonnull %.7.i23)
  call void @set_parallel_chunksize(i64 %.474)
  call void @deallocate_sched(ptr %.487)
  store ptr %.7.i.i.i, ptr %retptr, align 8
  %retptr.repack512 = getelementptr inbounds nuw i8, ptr %retptr, i64 8
  store ptr null, ptr %retptr.repack512, align 8
  %retptr.repack514 = getelementptr inbounds nuw i8, ptr %retptr, i64 16
  store i64 %arg.sim_thick_batch.5.0, ptr %retptr.repack514, align 8
  %retptr.repack516 = getelementptr inbounds nuw i8, ptr %retptr, i64 24
  store i64 8, ptr %retptr.repack516, align 8
  %retptr.repack518 = getelementptr inbounds nuw i8, ptr %retptr, i64 32
  store ptr %.6.i.i, ptr %retptr.repack518, align 8
  %retptr.repack520 = getelementptr inbounds nuw i8, ptr %retptr, i64 40
  store i64 %arg.sim_thick_batch.5.0, ptr %retptr.repack520, align 8
  %retptr.repack522 = getelementptr inbounds nuw i8, ptr %retptr, i64 48
  store i64 8, ptr %retptr.repack522, align 8
  call void @NRT_decref(ptr %arg.wls.0)
  call void @NRT_decref(ptr %arg.sim_thick_batch.0)
  call void @NRT_decref(ptr %arg.n_layers_flattened.0)
  call void @NRT_decref(ptr %arg.nSub_arr.0)
  call void @NRT_decref(ptr nonnull %.7.i.i.i7)
  call void @NRT_decref(ptr %arg.T_target.0)
  br label %common.ret
}

; Function Attrs: mustprogress nocallback nofree nounwind willreturn memory(argmem: write)
declare void @llvm.memset.p0.i64(ptr writeonly captures(none), i8, i64, i1 immarg) #0

declare i64 @get_sched_size(i64, i64, ptr, ptr) local_unnamed_addr

declare void @set_parallel_chunksize(i64) local_unnamed_addr

declare ptr @allocate_sched(i64) local_unnamed_addr

declare ptr @do_scheduling_unsigned(i64, ptr, ptr, i64, ptr, i64) local_unnamed_addr

declare void @deallocate_sched(ptr) local_unnamed_addr

declare i64 @get_num_threads() local_unnamed_addr

declare i64 @get_parallel_chunksize() local_unnamed_addr

; Function Attrs: nofree nounwind
declare noundef i32 @printf(ptr noundef readonly captures(none), ...) local_unnamed_addr #1

define ptr @_ZN7cpython6certus7physics18certus_strat_batch18compute_batch_rmseB2v1B126c8tJTC_2fWQAliW1xhDEoY6EEMEUOEMISPGsAQMVj4QniQ4IXKQEMXwoMGLoQDDVsQR1NHAS2hQ9XgStYwaUTI24JtBVoBDXtb9MCvVgdJqdcC7QJGJNxz8IQPcQgAE5ArrayIdLi2E1C7mutable7alignedE5ArrayIdLi1E1C7mutable7alignedE5ArrayI10complex128Li1E1C7mutable7alignedE5ArrayI10complex128Li1E1C7mutable7alignedE5ArrayI10complex128Li1E1C7mutable7alignedE5ArrayIdLi1E1C7mutable7alignedE5ArrayI10complex128Li2E1C7mutable7alignedEvN21omitted_28default_3d05_0_29E24omitted_28default_3d0_29N21omitted_28default_3d05_0_29EN21omitted_28default_3d05_0_29E(ptr readnone captures(none) %py_closure, ptr %py_args, ptr readnone captures(none) %py_kws) local_unnamed_addr {
entry:
  %.5 = alloca ptr, align 8
  %.6 = alloca ptr, align 8
  %.7 = alloca ptr, align 8
  %.8 = alloca ptr, align 8
  %.9 = alloca ptr, align 8
  %.10 = alloca ptr, align 8
  %.11 = alloca ptr, align 8
  %.12 = alloca ptr, align 8
  %.13 = alloca ptr, align 8
  %.14 = alloca ptr, align 8
  %.15 = alloca ptr, align 8
  %.16 = alloca ptr, align 8
  %.17 = call i32 (ptr, ptr, i64, i64, ...) @PyArg_UnpackTuple(ptr %py_args, ptr nonnull @.const.compute_batch_rmse, i64 12, i64 12, ptr nonnull %.5, ptr nonnull %.6, ptr nonnull %.7, ptr nonnull %.8, ptr nonnull %.9, ptr nonnull %.10, ptr nonnull %.11, ptr nonnull %.12, ptr nonnull %.13, ptr nonnull %.14, ptr nonnull %.15, ptr nonnull %.16)
  %.18 = icmp eq i32 %.17, 0
  %.30 = alloca { ptr, ptr, i64, i64, ptr, [2 x i64], [2 x i64] }, align 8
  %.55 = alloca { ptr, ptr, i64, i64, ptr, [1 x i64], [1 x i64] }, align 8
  %.78 = alloca { ptr, ptr, i64, i64, ptr, [1 x i64], [1 x i64] }, align 8
  %.101 = alloca { ptr, ptr, i64, i64, ptr, [1 x i64], [1 x i64] }, align 8
  %.124 = alloca { ptr, ptr, i64, i64, ptr, [1 x i64], [1 x i64] }, align 8
  %.147 = alloca { ptr, ptr, i64, i64, ptr, [1 x i64], [1 x i64] }, align 8
  %.170 = alloca { ptr, ptr, i64, i64, ptr, [2 x i64], [2 x i64] }, align 8
  %.199 = alloca { ptr, ptr, i64, i64, ptr, [1 x i64], [1 x i64] }, align 8
  %excinfo = alloca ptr, align 8
  call void @llvm.memset.p0.i64(ptr noundef nonnull align 8 dereferenceable(56) %.199, i8 0, i64 56, i1 false)
  store ptr null, ptr %excinfo, align 8
  %.297 = alloca { ptr, ptr, i64, i64, ptr, [1 x i64], [1 x i64] }, align 8
  call void @llvm.memset.p0.i64(ptr noundef nonnull align 8 dereferenceable(56) %.297, i8 0, i64 56, i1 false)
  br i1 %.18, label %common.ret, label %entry.endif, !prof !0

common.ret:                                       ; preds = %entry.endif.endif.endif.e...endif.2.endif.if.endif.if, %entry.endif.endif.endif.e...endif.2.endif.if.endif, %arg0.err, %entry.endif.endif.endif, %entry, %entry.endif.endif.endif.e...endif.2.endif.if.if.if, %entry.endif.endif.endif.e...endif.2.if.endif.endif, %entry.endif.if
  %common.ret.op = phi ptr [ null, %entry.endif.endif.endif.e...endif.2.endif.if.if.if ], [ null, %entry ], [ null, %entry.endif.if ], [ null, %entry.endif.endif.endif.e...endif.2.endif.if.endif ], [ %.301, %entry.endif.endif.endif.e...endif.2.if.endif.endif ], [ null, %arg0.err ], [ null, %entry.endif.endif.endif ], [ null, %entry.endif.endif.endif.e...endif.2.endif.if.endif.if ]
  ret ptr %common.ret.op

entry.endif:                                      ; preds = %entry
  %.22 = load ptr, ptr @_ZN08NumbaEnv6certus7physics18certus_strat_batch18compute_batch_rmseB2v1B126c8tJTC_2fWQAliW1xhDEoY6EEMEUOEMISPGsAQMVj4QniQ4IXKQEMXwoMGLoQDDVsQR1NHAS2hQ9XgStYwaUTI24JtBVoBDXtb9MCvVgdJqdcC7QJGJNxz8IQPcQgAE5ArrayIdLi2E1C7mutable7alignedE5ArrayIdLi1E1C7mutable7alignedE5ArrayI10complex128Li1E1C7mutable7alignedE5ArrayI10complex128Li1E1C7mutable7alignedE5ArrayI10complex128Li1E1C7mutable7alignedE5ArrayIdLi1E1C7mutable7alignedE5ArrayI10complex128Li2E1C7mutable7alignedEvN21omitted_28default_3d05_0_29E24omitted_28default_3d0_29N21omitted_28default_3d05_0_29EN21omitted_28default_3d05_0_29E, align 8
  %.25 = icmp eq ptr %.22, null
  br i1 %.25, label %entry.endif.if, label %entry.endif.endif, !prof !0

entry.endif.if:                                   ; preds = %entry.endif
  call void @PyErr_SetString(ptr nonnull @PyExc_RuntimeError, ptr nonnull @".const.missing Environment: _ZN08NumbaEnv6certus7physics18certus_strat_batch18compute_batch_rmseB2v1B126c8tJTC_2fWQAliW1xhDEoY6EEMEUOEMISPGsAQMVj4QniQ4IXKQEMXwoMGLoQDDVsQR1NHAS2hQ9XgStYwaUTI24JtBVoBDXtb9MCvVgdJqdcC7QJGJNxz8IQPcQgAE5ArrayIdLi2E1C7mutable7alignedE5ArrayIdLi1E1C7mutable7alignedE5ArrayI10complex128Li1E1C7mutable7alignedE5ArrayI10complex128Li1E1C7mutable7alignedE5ArrayI10complex128Li1E1C7mutable7alignedE5ArrayIdLi1E1C7mutable7alignedE5ArrayI10complex128Li2E1C7mutable7alignedEvN21omitted_28default_3d05_0_29E24omitted_28default_3d0_29N21omitted_28default_3d05_0_29EN21omitted_28default_3d05_0_29E")
  br label %common.ret

entry.endif.endif:                                ; preds = %entry.endif
  %.29 = load ptr, ptr %.5, align 8
  call void @llvm.memset.p0.i64(ptr noundef nonnull align 8 dereferenceable(72) %.30, i8 0, i64 72, i1 false)
  %.34 = call i32 @NRT_adapt_ndarray_from_python(ptr %.29, ptr nonnull %.30)
  %sunkaddr = getelementptr inbounds i8, ptr %.30, i64 24
  %.38 = load i64, ptr %sunkaddr, align 8
  %.39 = icmp ne i64 %.38, 8
  %.40 = icmp ne i32 %.34, 0
  %.41 = or i1 %.40, %.39
  br i1 %.41, label %entry.endif.endif.if, label %entry.endif.endif.endif, !prof !0

entry.endif.endif.if:                             ; preds = %entry.endif.endif
  call void @PyErr_SetString(ptr nonnull @PyExc_TypeError, ptr nonnull @".const.can't unbox array from PyObject into native value.  The object maybe of a different type")
  br label %entry.endif.endif.endif

entry.endif.endif.endif:                          ; preds = %entry.endif.endif.if, %entry.endif.endif
  %.45.fca.0.load = load ptr, ptr %.30, align 8
  %sunkaddr1 = getelementptr inbounds i8, ptr %.30, i64 32
  %.45.fca.4.load = load ptr, ptr %sunkaddr1, align 8
  %sunkaddr2 = getelementptr inbounds i8, ptr %.30, i64 40
  %.45.fca.5.0.load = load i64, ptr %sunkaddr2, align 8
  %sunkaddr3 = getelementptr inbounds i8, ptr %.30, i64 48
  %.45.fca.5.1.load = load i64, ptr %sunkaddr3, align 8
  %sunkaddr4 = getelementptr inbounds i8, ptr %.30, i64 56
  %.45.fca.6.0.load = load i64, ptr %sunkaddr4, align 8
  %sunkaddr5 = getelementptr inbounds i8, ptr %.30, i64 64
  %.45.fca.6.1.load = load i64, ptr %sunkaddr5, align 8
  br i1 %.41, label %common.ret, label %entry.endif.endif.endif.endif, !prof !0

entry.endif.endif.endif.endif:                    ; preds = %entry.endif.endif.endif
  %.54 = load ptr, ptr %.6, align 8
  call void @llvm.memset.p0.i64(ptr noundef nonnull align 8 dereferenceable(56) %.55, i8 0, i64 56, i1 false)
  %.59 = call i32 @NRT_adapt_ndarray_from_python(ptr %.54, ptr nonnull %.55)
  %sunkaddr6 = getelementptr inbounds i8, ptr %.55, i64 24
  %.63 = load i64, ptr %sunkaddr6, align 8
  %.64 = icmp ne i64 %.63, 8
  %.65 = icmp ne i32 %.59, 0
  %.66 = or i1 %.65, %.64
  br i1 %.66, label %entry.endif.endif.endif.endif.endif.thread, label %entry.endif.endif.endif.endif.endif.endif, !prof !0

arg0.err:                                         ; preds = %entry.endif.endif.endif.endif.endif.thread, %arg1.err
  call void @NRT_decref(ptr %.45.fca.0.load)
  br label %common.ret

entry.endif.endif.endif.endif.endif.thread:       ; preds = %entry.endif.endif.endif.endif
  call void @PyErr_SetString(ptr nonnull @PyExc_TypeError, ptr nonnull @".const.can't unbox array from PyObject into native value.  The object maybe of a different type")
  br label %arg0.err

entry.endif.endif.endif.endif.endif.endif:        ; preds = %entry.endif.endif.endif.endif
  %.70.fca.0.load = load ptr, ptr %.55, align 8
  %sunkaddr7 = getelementptr inbounds i8, ptr %.55, i64 32
  %.70.fca.4.load = load ptr, ptr %sunkaddr7, align 8
  %sunkaddr8 = getelementptr inbounds i8, ptr %.55, i64 40
  %.70.fca.5.0.load = load i64, ptr %sunkaddr8, align 8
  %sunkaddr9 = getelementptr inbounds i8, ptr %.55, i64 48
  %.70.fca.6.0.load = load i64, ptr %sunkaddr9, align 8
  %.77 = load ptr, ptr %.7, align 8
  call void @llvm.memset.p0.i64(ptr noundef nonnull align 8 dereferenceable(56) %.78, i8 0, i64 56, i1 false)
  %.82 = call i32 @NRT_adapt_ndarray_from_python(ptr %.77, ptr nonnull %.78)
  %sunkaddr10 = getelementptr inbounds i8, ptr %.78, i64 24
  %.86 = load i64, ptr %sunkaddr10, align 8
  %.87 = icmp ne i64 %.86, 16
  %.88 = icmp ne i32 %.82, 0
  %.89 = or i1 %.88, %.87
  br i1 %.89, label %entry.endif.endif.endif.endif.endif.endif.endif.thread, label %entry.endif.endif.endif.endif.endif.endif.endif.endif, !prof !0

arg1.err:                                         ; preds = %entry.endif.endif.endif.endif.endif.endif.endif.thread, %arg2.err
  call void @NRT_decref(ptr %.70.fca.0.load)
  br label %arg0.err

entry.endif.endif.endif.endif.endif.endif.endif.thread: ; preds = %entry.endif.endif.endif.endif.endif.endif
  call void @PyErr_SetString(ptr nonnull @PyExc_TypeError, ptr nonnull @".const.can't unbox array from PyObject into native value.  The object maybe of a different type")
  br label %arg1.err

entry.endif.endif.endif.endif.endif.endif.endif.endif: ; preds = %entry.endif.endif.endif.endif.endif.endif
  %.93.fca.0.load = load ptr, ptr %.78, align 8
  %.100 = load ptr, ptr %.8, align 8
  call void @llvm.memset.p0.i64(ptr noundef nonnull align 8 dereferenceable(56) %.101, i8 0, i64 56, i1 false)
  %.105 = call i32 @NRT_adapt_ndarray_from_python(ptr %.100, ptr nonnull %.101)
  %sunkaddr11 = getelementptr inbounds i8, ptr %.101, i64 24
  %.109 = load i64, ptr %sunkaddr11, align 8
  %.110 = icmp ne i64 %.109, 16
  %.111 = icmp ne i32 %.105, 0
  %.112 = or i1 %.111, %.110
  br i1 %.112, label %entry.endif.endif.endif.e...endif.thread, label %entry.endif.endif.endif.e...endif.endif, !prof !0

arg2.err:                                         ; preds = %entry.endif.endif.endif.e...endif.thread, %arg3.err
  call void @NRT_decref(ptr %.93.fca.0.load)
  br label %arg1.err

entry.endif.endif.endif.e...endif.thread:         ; preds = %entry.endif.endif.endif.endif.endif.endif.endif.endif
  call void @PyErr_SetString(ptr nonnull @PyExc_TypeError, ptr nonnull @".const.can't unbox array from PyObject into native value.  The object maybe of a different type")
  br label %arg2.err

entry.endif.endif.endif.e...endif.endif:          ; preds = %entry.endif.endif.endif.endif.endif.endif.endif.endif
  %.116.fca.0.load = load ptr, ptr %.101, align 8
  %.123 = load ptr, ptr %.9, align 8
  call void @llvm.memset.p0.i64(ptr noundef nonnull align 8 dereferenceable(56) %.124, i8 0, i64 56, i1 false)
  %.128 = call i32 @NRT_adapt_ndarray_from_python(ptr %.123, ptr nonnull %.124)
  %sunkaddr12 = getelementptr inbounds i8, ptr %.124, i64 24
  %.132 = load i64, ptr %sunkaddr12, align 8
  %.133 = icmp ne i64 %.132, 16
  %.134 = icmp ne i32 %.128, 0
  %.135 = or i1 %.134, %.133
  br i1 %.135, label %entry.endif.endif.endif.e...endif.endif.endif.thread, label %entry.endif.endif.endif.e...endif.endif.endif.endif, !prof !0

arg3.err:                                         ; preds = %entry.endif.endif.endif.e...endif.endif.endif.thread, %arg4.err
  call void @NRT_decref(ptr %.116.fca.0.load)
  br label %arg2.err

entry.endif.endif.endif.e...endif.endif.endif.thread: ; preds = %entry.endif.endif.endif.e...endif.endif
  call void @PyErr_SetString(ptr nonnull @PyExc_TypeError, ptr nonnull @".const.can't unbox array from PyObject into native value.  The object maybe of a different type")
  br label %arg3.err

entry.endif.endif.endif.e...endif.endif.endif.endif: ; preds = %entry.endif.endif.endif.e...endif.endif
  %.139.fca.0.load = load ptr, ptr %.124, align 8
  %sunkaddr13 = getelementptr inbounds i8, ptr %.124, i64 32
  %.139.fca.4.load = load ptr, ptr %sunkaddr13, align 8
  %sunkaddr14 = getelementptr inbounds i8, ptr %.124, i64 40
  %.139.fca.5.0.load = load i64, ptr %sunkaddr14, align 8
  %sunkaddr15 = getelementptr inbounds i8, ptr %.124, i64 48
  %.139.fca.6.0.load = load i64, ptr %sunkaddr15, align 8
  %.146 = load ptr, ptr %.10, align 8
  call void @llvm.memset.p0.i64(ptr noundef nonnull align 8 dereferenceable(56) %.147, i8 0, i64 56, i1 false)
  %.151 = call i32 @NRT_adapt_ndarray_from_python(ptr %.146, ptr nonnull %.147)
  %sunkaddr16 = getelementptr inbounds i8, ptr %.147, i64 24
  %.155 = load i64, ptr %sunkaddr16, align 8
  %.156 = icmp ne i64 %.155, 8
  %.157 = icmp ne i32 %.151, 0
  %.158 = or i1 %.157, %.156
  br i1 %.158, label %entry.endif.endif.endif.e...endif.1.thread, label %entry.endif.endif.endif.e...endif.1.endif, !prof !0

arg4.err:                                         ; preds = %entry.endif.endif.endif.e...endif.1.thread, %entry.endif.endif.endif.e...endif.1.endif.if
  call void @NRT_decref(ptr %.139.fca.0.load)
  br label %arg3.err

entry.endif.endif.endif.e...endif.1.thread:       ; preds = %entry.endif.endif.endif.e...endif.endif.endif.endif
  call void @PyErr_SetString(ptr nonnull @PyExc_TypeError, ptr nonnull @".const.can't unbox array from PyObject into native value.  The object maybe of a different type")
  br label %arg4.err

entry.endif.endif.endif.e...endif.1.endif:        ; preds = %entry.endif.endif.endif.e...endif.endif.endif.endif
  %.162.fca.0.load = load ptr, ptr %.147, align 8
  %sunkaddr17 = getelementptr inbounds i8, ptr %.147, i64 32
  %.162.fca.4.load = load ptr, ptr %sunkaddr17, align 8
  %sunkaddr18 = getelementptr inbounds i8, ptr %.147, i64 40
  %.162.fca.5.0.load = load i64, ptr %sunkaddr18, align 8
  %sunkaddr19 = getelementptr inbounds i8, ptr %.147, i64 48
  %.162.fca.6.0.load = load i64, ptr %sunkaddr19, align 8
  %.169 = load ptr, ptr %.11, align 8
  call void @llvm.memset.p0.i64(ptr noundef nonnull align 8 dereferenceable(72) %.170, i8 0, i64 72, i1 false)
  %.174 = call i32 @NRT_adapt_ndarray_from_python(ptr %.169, ptr nonnull %.170)
  %sunkaddr20 = getelementptr inbounds i8, ptr %.170, i64 24
  %.178 = load i64, ptr %sunkaddr20, align 8
  %.179 = icmp ne i64 %.178, 16
  %.180 = icmp ne i32 %.174, 0
  %.181 = or i1 %.180, %.179
  br i1 %.181, label %entry.endif.endif.endif.e...endif.1.endif.if, label %entry.endif.endif.endif.e...endif.2, !prof !0

entry.endif.endif.endif.e...endif.1.endif.if:     ; preds = %entry.endif.endif.endif.e...endif.1.endif
  call void @PyErr_SetString(ptr nonnull @PyExc_TypeError, ptr nonnull @".const.can't unbox array from PyObject into native value.  The object maybe of a different type")
  call void @NRT_decref(ptr %.162.fca.0.load)
  br label %arg4.err

entry.endif.endif.endif.e...endif.2:              ; preds = %entry.endif.endif.endif.e...endif.1.endif
  %.185.fca.0.load = load ptr, ptr %.170, align 8
  %sunkaddr21 = getelementptr inbounds i8, ptr %.170, i64 32
  %.185.fca.4.load = load ptr, ptr %sunkaddr21, align 8
  %sunkaddr22 = getelementptr inbounds i8, ptr %.170, i64 40
  %.185.fca.5.0.load = load i64, ptr %sunkaddr22, align 8
  %sunkaddr23 = getelementptr inbounds i8, ptr %.170, i64 48
  %.185.fca.5.1.load = load i64, ptr %sunkaddr23, align 8
  %sunkaddr24 = getelementptr inbounds i8, ptr %.170, i64 56
  %.185.fca.6.0.load = load i64, ptr %sunkaddr24, align 8
  %sunkaddr25 = getelementptr inbounds i8, ptr %.170, i64 64
  %.185.fca.6.1.load = load i64, ptr %sunkaddr25, align 8
  %.198 = call ptr @PyEval_SaveThread()
  call void @llvm.memset.p0.i64(ptr noundef nonnull align 8 dereferenceable(56) %.199, i8 0, i64 56, i1 false)
  %.221 = call i32 @_ZN6certus7physics18certus_strat_batch18compute_batch_rmseB2v1B126c8tJTC_2fWQAliW1xhDEoY6EEMEUOEMISPGsAQMVj4QniQ4IXKQEMXwoMGLoQDDVsQR1NHAS2hQ9XgStYwaUTI24JtBVoBDXtb9MCvVgdJqdcC7QJGJNxz8IQPcQgAE5ArrayIdLi2E1C7mutable7alignedE5ArrayIdLi1E1C7mutable7alignedE5ArrayI10complex128Li1E1C7mutable7alignedE5ArrayI10complex128Li1E1C7mutable7alignedE5ArrayI10complex128Li1E1C7mutable7alignedE5ArrayIdLi1E1C7mutable7alignedE5ArrayI10complex128Li2E1C7mutable7alignedEvN21omitted_28default_3d05_0_29E24omitted_28default_3d0_29N21omitted_28default_3d05_0_29EN21omitted_28default_3d05_0_29E(ptr nonnull %.199, ptr nonnull %excinfo, ptr %.45.fca.0.load, ptr poison, i64 poison, i64 poison, ptr %.45.fca.4.load, i64 %.45.fca.5.0.load, i64 %.45.fca.5.1.load, i64 %.45.fca.6.0.load, i64 %.45.fca.6.1.load, ptr %.70.fca.0.load, ptr poison, i64 poison, i64 poison, ptr %.70.fca.4.load, i64 %.70.fca.5.0.load, i64 %.70.fca.6.0.load, ptr poison, ptr poison, i64 poison, i64 poison, ptr poison, i64 poison, i64 poison, ptr poison, ptr poison, i64 poison, i64 poison, ptr poison, i64 poison, i64 poison, ptr %.139.fca.0.load, ptr poison, i64 poison, i64 poison, ptr %.139.fca.4.load, i64 %.139.fca.5.0.load, i64 %.139.fca.6.0.load, ptr %.162.fca.0.load, ptr poison, i64 poison, i64 poison, ptr %.162.fca.4.load, i64 %.162.fca.5.0.load, i64 %.162.fca.6.0.load, ptr %.185.fca.0.load, ptr poison, i64 poison, i64 poison, ptr %.185.fca.4.load, i64 %.185.fca.5.0.load, i64 %.185.fca.5.1.load, i64 %.185.fca.6.0.load, i64 %.185.fca.6.1.load, ptr poison) #3
  %.222 = load ptr, ptr %excinfo, align 8
  %.231.fca.0.load = load ptr, ptr %.199, align 8
  %sunkaddr26 = getelementptr inbounds i8, ptr %.199, i64 8
  %.231.fca.1.load = load ptr, ptr %sunkaddr26, align 8
  %sunkaddr27 = getelementptr inbounds i8, ptr %.199, i64 16
  %.231.fca.2.load = load i64, ptr %sunkaddr27, align 8
  %sunkaddr28 = getelementptr inbounds i8, ptr %.199, i64 24
  %.231.fca.3.load = load i64, ptr %sunkaddr28, align 8
  %sunkaddr29 = getelementptr inbounds i8, ptr %.199, i64 32
  %.231.fca.4.load = load ptr, ptr %sunkaddr29, align 8
  %sunkaddr30 = getelementptr inbounds i8, ptr %.199, i64 40
  %.231.fca.5.0.load = load i64, ptr %sunkaddr30, align 8
  %sunkaddr31 = getelementptr inbounds i8, ptr %.199, i64 48
  %.231.fca.6.0.load = load i64, ptr %sunkaddr31, align 8
  call void @PyEval_RestoreThread(ptr %.198)
  call void @NRT_decref(ptr %.45.fca.0.load)
  call void @NRT_decref(ptr %.70.fca.0.load)
  call void @NRT_decref(ptr %.93.fca.0.load)
  call void @NRT_decref(ptr %.116.fca.0.load)
  call void @NRT_decref(ptr %.139.fca.0.load)
  call void @NRT_decref(ptr %.162.fca.0.load)
  call void @NRT_decref(ptr %.185.fca.0.load)
  %cond = icmp eq i32 %.221, 0
  br i1 %cond, label %entry.endif.endif.endif.e...endif.2.if.endif, label %entry.endif.endif.endif.e...endif.2.endif.if, !prof !24

entry.endif.endif.endif.e...endif.2.if.endif:     ; preds = %entry.endif.endif.endif.e...endif.2
  %.277 = getelementptr i8, ptr %.22, i64 24
  %.278 = load ptr, ptr %.277, align 8
  %.282.not = icmp eq ptr %.278, null
  br i1 %.282.not, label %entry.endif.endif.endif.e...endif.2.if.endif.else, label %entry.endif.endif.endif.e...endif.2.if.endif.if

entry.endif.endif.endif.e...endif.2.if.endif.if:  ; preds = %entry.endif.endif.endif.e...endif.2.if.endif
  %.284 = call ptr @PyList_GetItem(ptr nonnull %.278, i64 0)
  br label %entry.endif.endif.endif.e...endif.2.if.endif.endif

entry.endif.endif.endif.e...endif.2.if.endif.else: ; preds = %entry.endif.endif.endif.e...endif.2.if.endif
  call void @PyErr_SetString(ptr nonnull @PyExc_RuntimeError, ptr nonnull @".const.`env.consts` is NULL in `read_const`")
  br label %entry.endif.endif.endif.e...endif.2.if.endif.endif

entry.endif.endif.endif.e...endif.2.if.endif.endif: ; preds = %entry.endif.endif.endif.e...endif.2.if.endif.else, %entry.endif.endif.endif.e...endif.2.if.endif.if
  %.279.0 = phi ptr [ %.284, %entry.endif.endif.endif.e...endif.2.if.endif.if ], [ null, %entry.endif.endif.endif.e...endif.2.if.endif.else ]
  %.296 = call ptr @numba_unpickle(ptr nonnull @.const.pickledata.dfbcfdd39fcb26f4d0c680954487b8c0b53bb8a3, i32 32, ptr nonnull @.const.pickledata.dfbcfdd39fcb26f4d0c680954487b8c0b53bb8a3.sha1)
  store ptr %.231.fca.0.load, ptr %.297, align 8
  %sunkaddr32 = getelementptr inbounds i8, ptr %.297, i64 8
  store ptr %.231.fca.1.load, ptr %sunkaddr32, align 8
  %sunkaddr33 = getelementptr inbounds i8, ptr %.297, i64 16
  store i64 %.231.fca.2.load, ptr %sunkaddr33, align 8
  %sunkaddr34 = getelementptr inbounds i8, ptr %.297, i64 24
  store i64 %.231.fca.3.load, ptr %sunkaddr34, align 8
  %sunkaddr35 = getelementptr inbounds i8, ptr %.297, i64 32
  store ptr %.231.fca.4.load, ptr %sunkaddr35, align 8
  %sunkaddr36 = getelementptr inbounds i8, ptr %.297, i64 40
  store i64 %.231.fca.5.0.load, ptr %sunkaddr36, align 8
  %sunkaddr37 = getelementptr inbounds i8, ptr %.297, i64 48
  store i64 %.231.fca.6.0.load, ptr %sunkaddr37, align 8
  %.301 = call ptr @NRT_adapt_ndarray_to_python_acqref(ptr nonnull %.297, ptr %.296, i32 1, i32 1, ptr %.279.0)
  call void @NRT_decref(ptr %.231.fca.0.load)
  br label %common.ret

entry.endif.endif.endif.e...endif.2.endif.if:     ; preds = %entry.endif.endif.endif.e...endif.2
  call void @PyErr_Clear()
  %.309 = load { ptr, i32, ptr, ptr, i32 }, ptr %.222, align 8
  %.310 = extractvalue { ptr, i32, ptr, ptr, i32 } %.309, 4
  %.311 = icmp sgt i32 %.310, 0
  %.314 = extractvalue { ptr, i32, ptr, ptr, i32 } %.309, 0
  %.316 = extractvalue { ptr, i32, ptr, ptr, i32 } %.309, 1
  br i1 %.311, label %entry.endif.endif.endif.e...endif.2.endif.if.if, label %entry.endif.endif.endif.e...endif.2.endif.if.else

entry.endif.endif.endif.e...endif.2.endif.if.if:  ; preds = %entry.endif.endif.endif.e...endif.2.endif.if
  %.317 = sext i32 %.316 to i64
  %.318 = call ptr @PyBytes_FromStringAndSize(ptr %.314, i64 %.317)
  %.319 = load { ptr, i32, ptr, ptr, i32 }, ptr %.222, align 8
  %.320 = extractvalue { ptr, i32, ptr, ptr, i32 } %.319, 2
  %.322 = extractvalue { ptr, i32, ptr, ptr, i32 } %.319, 3
  %.324 = call ptr %.322(ptr %.320)
  %.325 = icmp eq ptr %.324, null
  br i1 %.325, label %entry.endif.endif.endif.e...endif.2.endif.if.if.if, label %entry.endif.endif.endif.e...endif.2.endif.if.if.endif, !prof !0

entry.endif.endif.endif.e...endif.2.endif.if.else: ; preds = %entry.endif.endif.endif.e...endif.2.endif.if
  %.338 = extractvalue { ptr, i32, ptr, ptr, i32 } %.309, 2
  %.339 = call ptr @numba_unpickle(ptr %.314, i32 %.316, ptr %.338)
  br label %entry.endif.endif.endif.e...endif.2.endif.if.endif

entry.endif.endif.endif.e...endif.2.endif.if.endif: ; preds = %entry.endif.endif.endif.e...endif.2.endif.if.if.endif, %entry.endif.endif.endif.e...endif.2.endif.if.else
  %.341 = phi ptr [ %.329, %entry.endif.endif.endif.e...endif.2.endif.if.if.endif ], [ %.339, %entry.endif.endif.endif.e...endif.2.endif.if.else ]
  %.342.not = icmp eq ptr %.341, null
  br i1 %.342.not, label %common.ret, label %entry.endif.endif.endif.e...endif.2.endif.if.endif.if, !prof !0

entry.endif.endif.endif.e...endif.2.endif.if.if.if: ; preds = %entry.endif.endif.endif.e...endif.2.endif.if.if
  call void @PyErr_SetString(ptr nonnull @PyExc_RuntimeError, ptr nonnull @".const.Error creating Python tuple from runtime exception arguments")
  br label %common.ret

entry.endif.endif.endif.e...endif.2.endif.if.if.endif: ; preds = %entry.endif.endif.endif.e...endif.2.endif.if.if
  %.329 = call ptr @numba_runtime_build_excinfo_struct(ptr %.318, ptr nonnull %.324)
  call void @NRT_Free(ptr nonnull %.222)
  br label %entry.endif.endif.endif.e...endif.2.endif.if.endif

entry.endif.endif.endif.e...endif.2.endif.if.endif.if: ; preds = %entry.endif.endif.endif.e...endif.2.endif.if.endif
  call void @numba_do_raise(ptr nonnull %.341)
  br label %common.ret
}

declare i32 @PyArg_UnpackTuple(ptr, ptr, i64, i64, ...) local_unnamed_addr

declare void @PyErr_SetString(ptr, ptr) local_unnamed_addr

declare i32 @NRT_adapt_ndarray_from_python(ptr captures(none), ptr captures(none)) local_unnamed_addr

declare ptr @PyEval_SaveThread() local_unnamed_addr

declare void @PyEval_RestoreThread(ptr) local_unnamed_addr

declare ptr @PyList_GetItem(ptr, i64) local_unnamed_addr

declare ptr @numba_unpickle(ptr, i32, ptr) local_unnamed_addr

declare ptr @NRT_adapt_ndarray_to_python_acqref(ptr captures(none), ptr, i32, i32, ptr) local_unnamed_addr

declare void @PyErr_Clear() local_unnamed_addr

declare ptr @PyBytes_FromStringAndSize(ptr, i64) local_unnamed_addr

declare ptr @numba_runtime_build_excinfo_struct(ptr, ptr) local_unnamed_addr

declare void @NRT_Free(ptr) local_unnamed_addr

declare void @numba_do_raise(ptr) local_unnamed_addr

declare void @PyErr_SetNone(ptr) local_unnamed_addr

declare noalias ptr @NRT_MemInfo_alloc_aligned(i64, i32) local_unnamed_addr

declare void @numba_gil_ensure(ptr) local_unnamed_addr

define weak_odr void @__gufunc__._ZN13_3cdynamic_3e35__numba_parfor_gufunc_0x24b561942f0B3v23B138c8tJTC_2fWQAliW1xhDEoY6EEMEUOEMISPGsAQMVj4QniQ4IXKQEMXwoMGLoQDDVsQR1NHAS2hQ9XgStYwaUTI24JtBVoBDXtb9MCvVgdJqdcC7YLGAMy5RSVwr8KzAcRZAA_3d_3dE5ArrayIyLi1E1C7mutable7alignedE5ArrayIdLi1E1C7mutable7alignedE5ArrayIdLi1E1C7mutable7alignedE(ptr %args, ptr %dims, ptr %steps, ptr %data) {
entry:
  %loopcount = load i64, ptr %dims, align 8
  %data.1 = load ptr, ptr %args, align 8
  %.10 = load i64, ptr %steps, align 8
  %core.step.ptr.1 = getelementptr i8, ptr %steps, i64 8
  %.12 = load i64, ptr %core.step.ptr.1, align 8
  %core.step.ptr.2 = getelementptr i8, ptr %steps, i64 16
  %.14 = load i64, ptr %core.step.ptr.2, align 8
  %.1722 = icmp sgt i64 %loopcount, 0
  br i1 %.1722, label %for.body.preheader, label %common.ret

for.body.preheader:                               ; preds = %entry
  %const = bitcast i64 9223372036854775804 to i64
  %data.ptr.2 = getelementptr i8, ptr %args, i64 16
  %data.3 = load ptr, ptr %data.ptr.2, align 8
  %data.ptr.1 = getelementptr i8, ptr %args, i64 8
  %data.2 = load ptr, ptr %data.ptr.1, align 8
  br label %for.body

common.ret:                                       ; preds = %.continue, %entry
  ret void

for.body:                                         ; preds = %.continue, %for.body.preheader
  %lsr.iv4 = phi ptr [ %data.2, %for.body.preheader ], [ %scevgep5, %.continue ]
  %lsr.iv = phi ptr [ %data.3, %for.body.preheader ], [ %scevgep, %.continue ]
  %loop.index23 = phi i64 [ 0, %for.body.preheader ], [ %.176, %.continue ]
  %.22 = mul i64 %loop.index23, %.10
  %.23 = getelementptr i8, ptr %data.1, i64 %.22
  tail call void @llvm.experimental.noalias.scope.decl(metadata !25)
  tail call void @llvm.experimental.noalias.scope.decl(metadata !28)
  tail call void @llvm.experimental.noalias.scope.decl(metadata !30)
  %.82.i = load i64, ptr %.23, align 8, !alias.scope !25, !noalias !32
  %.120.i = getelementptr i8, ptr %.23, i64 8
  %.121.i = load i64, ptr %.120.i, align 8, !alias.scope !25, !noalias !32
  %reass.sub.i = sub i64 %.121.i, %.82.i
  %const_mat = add i64 %const, 3
  %.259140144.i = icmp ult i64 %reass.sub.i, %const_mat
  br i1 %.259140144.i, label %B112.preheader.i, label %.continue

B112.preheader.i:                                 ; preds = %for.body
  %.212.i = add nuw nsw i64 %reass.sub.i, 1
  %min.iters.check.i = icmp samesign ult i64 %reass.sub.i, 3
  br i1 %min.iters.check.i, label %B112.preheader2.i, label %vector.ph.i

vector.ph.i:                                      ; preds = %B112.preheader.i
  %n.vec.i = and i64 %.212.i, %const
  %0 = shl i64 %.82.i, 3
  %scevgep2 = getelementptr i8, ptr %lsr.iv, i64 %0
  %scevgep6 = getelementptr i8, ptr %lsr.iv4, i64 %0
  br label %vector.body.i

vector.body.i:                                    ; preds = %vector.body.i, %vector.ph.i
  %index.i = phi i64 [ 0, %vector.ph.i ], [ %index.next.i, %vector.body.i ]
  %1 = shl i64 %index.i, 3
  %scevgep7 = getelementptr i8, ptr %scevgep6, i64 %1
  %wide.load.i = load <4 x double>, ptr %scevgep7, align 8, !alias.scope !28, !noalias !34
  %2 = fdiv fast <4 x double> splat (double 0x401921FB54442D18), %wide.load.i
  %scevgep3 = getelementptr i8, ptr %scevgep2, i64 %1
  store <4 x double> %2, ptr %scevgep3, align 8, !alias.scope !30, !noalias !35
  %index.next.i = add nuw nsw i64 %index.i, 4
  %3 = icmp eq i64 %n.vec.i, %index.next.i
  br i1 %3, label %middle.block.i, label %vector.body.i, !llvm.loop !36

middle.block.i:                                   ; preds = %vector.body.i
  %4 = and i64 %.212.i, 3
  %5 = add i64 %n.vec.i, %.82.i
  %cmp.n.i = icmp eq i64 %.212.i, %n.vec.i
  br i1 %cmp.n.i, label %.continue, label %B112.preheader2.i

B112.preheader2.i:                                ; preds = %middle.block.i, %B112.preheader.i
  %.258138142.ph.i = phi i64 [ %.212.i, %B112.preheader.i ], [ %4, %middle.block.i ]
  %.265139141.ph.i = phi i64 [ %.82.i, %B112.preheader.i ], [ %5, %middle.block.i ]
  %6 = add nuw nsw i64 %.258138142.ph.i, 1
  %7 = shl i64 %.265139141.ph.i, 3
  br label %B112.i

B112.i:                                           ; preds = %B112.i, %B112.preheader2.i
  %lsr.iv3.i = phi i64 [ %7, %B112.preheader2.i ], [ %lsr.iv.next4.i, %B112.i ]
  %lsr.iv.i = phi i64 [ %6, %B112.preheader2.i ], [ %lsr.iv.next.i, %B112.i ]
  %scevgep9 = getelementptr i8, ptr %lsr.iv4, i64 %lsr.iv3.i
  %.334.i = load double, ptr %scevgep9, align 8, !alias.scope !28, !noalias !34
  %8 = fdiv fast double 0x401921FB54442D18, %.334.i
  %scevgep8 = getelementptr i8, ptr %lsr.iv, i64 %lsr.iv3.i
  store double %8, ptr %scevgep8, align 8, !alias.scope !30, !noalias !35
  %lsr.iv.next.i = add i64 %lsr.iv.i, -1
  %lsr.iv.next4.i = add i64 %lsr.iv3.i, 8
  %.259.i = icmp samesign ugt i64 %lsr.iv.next.i, 1
  br i1 %.259.i, label %B112.i, label %.continue, !llvm.loop !39

.continue:                                        ; preds = %B112.i, %middle.block.i, %for.body
  %.176 = add nuw nsw i64 %loop.index23, 1
  %scevgep = getelementptr i8, ptr %lsr.iv, i64 %.14
  %scevgep5 = getelementptr i8, ptr %lsr.iv4, i64 %.12
  %exitcond.not = icmp eq i64 %.176, %loopcount
  br i1 %exitcond.not, label %common.ret, label %for.body
}

declare void @numba_parallel_for(ptr, ptr, ptr, ptr, ptr, i64, i64, i64) local_unnamed_addr

declare void @numba_gil_release(ptr) local_unnamed_addr

; Function Attrs: mustprogress nocallback nofree nosync nounwind willreturn memory(inaccessiblemem: readwrite)
declare void @llvm.experimental.noalias.scope.decl(metadata) #2

; Function Attrs: noinline
define linkonce_odr void @NRT_decref(ptr %.1) local_unnamed_addr #3 {
.3:
  %.4 = icmp eq ptr %.1, null
  br i1 %.4, label %common.ret, label %.3.endif, !prof !0

common.ret:                                       ; preds = %.3, %.3.endif
  ret void

.3.endif:                                         ; preds = %.3
  fence release
  %0 = tail call i8 @llvm.x86.atomic.sub.cc.i64(ptr nonnull %.1, i64 1, i32 4)
  %1 = trunc i8 %0 to i1
  br i1 %1, label %.3.endif.if, label %common.ret, !prof !0

.3.endif.if:                                      ; preds = %.3.endif
  fence acquire
  tail call void @NRT_MemInfo_call_dtor(ptr nonnull %.1)
  ret void
}

; Function Attrs: nounwind
declare i8 @llvm.x86.atomic.sub.cc.i64(ptr, i64, i32 immarg) #4

declare void @NRT_MemInfo_call_dtor(ptr) local_unnamed_addr

define weak_odr void @__gufunc__._ZN13_3cdynamic_3e35__numba_parfor_gufunc_0x24b56214910B3v24B126c8tJTC_2fWQAliW1xhDEoY6EEMEUOEMISPGsAQMVj4QniQ4IXKQEMXwoMGLoQDDVsQR1NHAS2hQ9XgStYwaUTI24JtBVoBDXtb9MCvVgdJqdcC7QJGJNxz8IQPcQgAE5ArrayIyLi1E1C7mutable7alignedEb5ArrayIdLi1E1C7mutable7alignedEddd23Literal_5bint_5d_280_295ArrayIdLi1E1C7mutable7alignedE5ArrayI10complex128Li1E1C7mutable7alignedEx5ArrayI10complex128Li2E1C7mutable7alignedE5ArrayIdLi2E1C7mutable7alignedE5ArrayIdLi1E1C7mutable7alignedEx5ArrayIdLi1E1C7mutable7alignedE(ptr %args, ptr %dims, ptr %steps, ptr %data) {
entry:
  %loopcount = load i64, ptr %dims, align 8
  %.6 = getelementptr i8, ptr %dims, i64 8
  %.7 = load i64, ptr %.6, align 8
  %.8 = getelementptr i8, ptr %dims, i64 16
  %.9 = load i64, ptr %.8, align 8
  %.10 = getelementptr i8, ptr %dims, i64 24
  %.11 = load i64, ptr %.10, align 8
  %.12 = getelementptr i8, ptr %dims, i64 32
  %.13 = load i64, ptr %.12, align 8
  %.14 = getelementptr i8, ptr %dims, i64 40
  %.15 = load i64, ptr %.14, align 8
  %.16 = getelementptr i8, ptr %dims, i64 48
  %.17 = load i64, ptr %.16, align 8
  %.18 = getelementptr i8, ptr %dims, i64 56
  %.19 = load i64, ptr %.18, align 8
  %.20 = getelementptr i8, ptr %dims, i64 64
  %.21 = load i64, ptr %.20, align 8
  %data.1 = load ptr, ptr %args, align 8
  %.22 = load i64, ptr %steps, align 8
  %step.ptr = getelementptr i8, ptr %steps, i64 120
  %.23 = load i64, ptr %step.ptr, align 8
  %data.ptr.1 = getelementptr i8, ptr %args, i64 8
  %data.2 = load ptr, ptr %data.ptr.1, align 8
  %core.step.ptr.1 = getelementptr i8, ptr %steps, i64 8
  %.24 = load i64, ptr %core.step.ptr.1, align 8
  %data.ptr.2 = getelementptr i8, ptr %args, i64 16
  %data.3 = load ptr, ptr %data.ptr.2, align 8
  %core.step.ptr.2 = getelementptr i8, ptr %steps, i64 16
  %.25 = load i64, ptr %core.step.ptr.2, align 8
  %step.ptr.1 = getelementptr i8, ptr %steps, i64 128
  %.26 = load i64, ptr %step.ptr.1, align 8
  %data.ptr.3 = getelementptr i8, ptr %args, i64 24
  %data.4 = load ptr, ptr %data.ptr.3, align 8
  %core.step.ptr.3 = getelementptr i8, ptr %steps, i64 24
  %.27 = load i64, ptr %core.step.ptr.3, align 8
  %data.ptr.4 = getelementptr i8, ptr %args, i64 32
  %data.5 = load ptr, ptr %data.ptr.4, align 8
  %core.step.ptr.4 = getelementptr i8, ptr %steps, i64 32
  %.28 = load i64, ptr %core.step.ptr.4, align 8
  %data.ptr.5 = getelementptr i8, ptr %args, i64 40
  %data.6 = load ptr, ptr %data.ptr.5, align 8
  %core.step.ptr.5 = getelementptr i8, ptr %steps, i64 40
  %.29 = load i64, ptr %core.step.ptr.5, align 8
  %data.ptr.6 = getelementptr i8, ptr %args, i64 48
  %data.7 = load ptr, ptr %data.ptr.6, align 8
  %core.step.ptr.6 = getelementptr i8, ptr %steps, i64 48
  %.30 = load i64, ptr %core.step.ptr.6, align 8
  %data.ptr.7 = getelementptr i8, ptr %args, i64 56
  %data.8 = load ptr, ptr %data.ptr.7, align 8
  %core.step.ptr.7 = getelementptr i8, ptr %steps, i64 56
  %.31 = load i64, ptr %core.step.ptr.7, align 8
  %step.ptr.2 = getelementptr i8, ptr %steps, i64 136
  %.32 = load i64, ptr %step.ptr.2, align 8
  %data.ptr.8 = getelementptr i8, ptr %args, i64 64
  %data.9 = load ptr, ptr %data.ptr.8, align 8
  %core.step.ptr.8 = getelementptr i8, ptr %steps, i64 64
  %.33 = load i64, ptr %core.step.ptr.8, align 8
  %step.ptr.3 = getelementptr i8, ptr %steps, i64 144
  %.34 = load i64, ptr %step.ptr.3, align 8
  %data.ptr.9 = getelementptr i8, ptr %args, i64 72
  %data.10 = load ptr, ptr %data.ptr.9, align 8
  %core.step.ptr.9 = getelementptr i8, ptr %steps, i64 72
  %.35 = load i64, ptr %core.step.ptr.9, align 8
  %data.ptr.10 = getelementptr i8, ptr %args, i64 80
  %data.11 = load ptr, ptr %data.ptr.10, align 8
  %core.step.ptr.10 = getelementptr i8, ptr %steps, i64 80
  %.36 = load i64, ptr %core.step.ptr.10, align 8
  %step.ptr.4 = getelementptr i8, ptr %steps, i64 152
  %.37 = load i64, ptr %step.ptr.4, align 8
  %step.ptr.5 = getelementptr i8, ptr %steps, i64 160
  %.38 = load i64, ptr %step.ptr.5, align 8
  %data.ptr.11 = getelementptr i8, ptr %args, i64 88
  %data.12 = load ptr, ptr %data.ptr.11, align 8
  %core.step.ptr.11 = getelementptr i8, ptr %steps, i64 88
  %.39 = load i64, ptr %core.step.ptr.11, align 8
  %step.ptr.6 = getelementptr i8, ptr %steps, i64 168
  %.40 = load i64, ptr %step.ptr.6, align 8
  %step.ptr.7 = getelementptr i8, ptr %steps, i64 176
  %.41 = load i64, ptr %step.ptr.7, align 8
  %data.ptr.12 = getelementptr i8, ptr %args, i64 96
  %data.13 = load ptr, ptr %data.ptr.12, align 8
  %core.step.ptr.12 = getelementptr i8, ptr %steps, i64 96
  %.42 = load i64, ptr %core.step.ptr.12, align 8
  %step.ptr.8 = getelementptr i8, ptr %steps, i64 184
  %.43 = load i64, ptr %step.ptr.8, align 8
  %data.ptr.13 = getelementptr i8, ptr %args, i64 104
  %data.14 = load ptr, ptr %data.ptr.13, align 8
  %core.step.ptr.13 = getelementptr i8, ptr %steps, i64 104
  %.44 = load i64, ptr %core.step.ptr.13, align 8
  %data.ptr.14 = getelementptr i8, ptr %args, i64 112
  %data.15 = load ptr, ptr %data.ptr.14, align 8
  %core.step.ptr.14 = getelementptr i8, ptr %steps, i64 112
  %.45 = load i64, ptr %core.step.ptr.14, align 8
  %step.ptr.9 = getelementptr i8, ptr %steps, i64 192
  %.46 = load i64, ptr %step.ptr.9, align 8
  %.301 = alloca ptr, align 8
  %excinfo = alloca ptr, align 8
  store ptr null, ptr %excinfo, align 8
  %.337 = alloca i32, align 4
  store i32 0, ptr %.337, align 4
  %.4861 = icmp sgt i64 %loopcount, 0
  br i1 %.4861, label %for.body.lr.ph, label %common.ret

for.body.lr.ph:                                   ; preds = %entry
  %.196 = mul nsw i64 %.17, %.15
  %.227 = mul nsw i64 %.21, %.19
  br label %for.body

common.ret:                                       ; preds = %.continue, %for.body.if.if.if.if, %for.body.endif.thread, %entry
  ret void

for.body:                                         ; preds = %.continue, %for.body.lr.ph
  %lsr.iv36 = phi i64 [ %loopcount, %for.body.lr.ph ], [ %lsr.iv.next, %.continue ]
  %lsr.iv34 = phi ptr [ %data.15, %for.body.lr.ph ], [ %scevgep35, %.continue ]
  %lsr.iv32 = phi ptr [ %data.14, %for.body.lr.ph ], [ %scevgep33, %.continue ]
  %lsr.iv30 = phi ptr [ %data.13, %for.body.lr.ph ], [ %scevgep31, %.continue ]
  %lsr.iv28 = phi ptr [ %data.12, %for.body.lr.ph ], [ %scevgep29, %.continue ]
  %lsr.iv26 = phi ptr [ %data.11, %for.body.lr.ph ], [ %scevgep27, %.continue ]
  %lsr.iv24 = phi ptr [ %data.10, %for.body.lr.ph ], [ %scevgep25, %.continue ]
  %lsr.iv22 = phi ptr [ %data.9, %for.body.lr.ph ], [ %scevgep23, %.continue ]
  %lsr.iv20 = phi ptr [ %data.8, %for.body.lr.ph ], [ %scevgep21, %.continue ]
  %lsr.iv18 = phi ptr [ %data.7, %for.body.lr.ph ], [ %scevgep19, %.continue ]
  %lsr.iv16 = phi ptr [ %data.6, %for.body.lr.ph ], [ %scevgep17, %.continue ]
  %lsr.iv14 = phi ptr [ %data.5, %for.body.lr.ph ], [ %scevgep15, %.continue ]
  %lsr.iv12 = phi ptr [ %data.4, %for.body.lr.ph ], [ %scevgep13, %.continue ]
  %lsr.iv10 = phi ptr [ %data.3, %for.body.lr.ph ], [ %scevgep11, %.continue ]
  %lsr.iv8 = phi ptr [ %data.2, %for.body.lr.ph ], [ %scevgep9, %.continue ]
  %lsr.iv = phi ptr [ %data.1, %for.body.lr.ph ], [ %scevgep, %.continue ]
  %.79 = load i8, ptr %lsr.iv8, align 1
  %.110 = load double, ptr %lsr.iv12, align 8
  %.114 = load double, ptr %lsr.iv14, align 8
  %.118 = load double, ptr %lsr.iv16, align 8
  %.122 = load i64, ptr %lsr.iv18, align 8
  %.180 = load i64, ptr %lsr.iv24, align 8
  %.273 = load i64, ptr %lsr.iv32, align 8
  %.325 = call i32 @_ZN13_3cdynamic_3e35__numba_parfor_gufunc_0x24b56214910B3v24B126c8tJTC_2fWQAliW1xhDEoY6EEMEUOEMISPGsAQMVj4QniQ4IXKQEMXwoMGLoQDDVsQR1NHAS2hQ9XgStYwaUTI24JtBVoBDXtb9MCvVgdJqdcC7QJGJNxz8IQPcQgAE5ArrayIyLi1E1C7mutable7alignedEb5ArrayIdLi1E1C7mutable7alignedEddd23Literal_5bint_5d_280_295ArrayIdLi1E1C7mutable7alignedE5ArrayI10complex128Li1E1C7mutable7alignedEx5ArrayI10complex128Li2E1C7mutable7alignedE5ArrayIdLi2E1C7mutable7alignedE5ArrayIdLi1E1C7mutable7alignedEx5ArrayIdLi1E1C7mutable7alignedE(ptr nonnull %.301, ptr nonnull %excinfo, ptr null, ptr null, i64 %.7, i64 8, ptr %lsr.iv, i64 %.7, i64 %.23, i8 %.79, ptr null, ptr null, i64 %.9, i64 8, ptr %lsr.iv10, i64 %.9, i64 %.26, double %.110, double %.114, double %.118, i64 %.122, ptr null, ptr null, i64 %.11, i64 8, ptr %lsr.iv20, i64 %.11, i64 %.32, ptr null, ptr null, i64 %.13, i64 16, ptr %lsr.iv22, i64 %.13, i64 %.34, i64 %.180, ptr null, ptr null, i64 %.196, i64 16, ptr %lsr.iv26, i64 %.15, i64 %.17, i64 %.37, i64 %.38, ptr null, ptr null, i64 %.227, i64 8, ptr %lsr.iv28, i64 %.19, i64 %.21, i64 %.40, i64 %.41, ptr null, ptr null, i64 %.11, i64 8, ptr %lsr.iv30, i64 %.11, i64 %.43, i64 %.273, ptr null, ptr null, i64 %.19, i64 8, ptr %lsr.iv34, i64 %.19, i64 %.46)
  %cond = icmp eq i32 %.325, 0
  br i1 %cond, label %.continue, label %for.body.if, !prof !24

for.body.if:                                      ; preds = %for.body
  %.326.le = load ptr, ptr %excinfo, align 8
  %.333 = icmp sgt i32 %.325, 0
  call void @numba_gil_ensure(ptr nonnull %.337)
  br i1 %.333, label %for.body.if.if, label %for.body.if.endif

for.body.endif.thread:                            ; preds = %for.body.if.endif.endif.endif, %for.body.if.endif.if, %for.body.if.if.endif.if, %for.body.if.if.endif, %for.body.if.endif
  call void @numba_gil_release(ptr nonnull %.337)
  br label %common.ret

for.body.if.if:                                   ; preds = %for.body.if
  call void @PyErr_Clear()
  %.343 = load { ptr, i32, ptr, ptr, i32 }, ptr %.326.le, align 8
  %.344 = extractvalue { ptr, i32, ptr, ptr, i32 } %.343, 4
  %.345 = icmp sgt i32 %.344, 0
  %.348 = extractvalue { ptr, i32, ptr, ptr, i32 } %.343, 0
  %.350 = extractvalue { ptr, i32, ptr, ptr, i32 } %.343, 1
  br i1 %.345, label %for.body.if.if.if, label %for.body.if.if.else

for.body.if.endif:                                ; preds = %for.body.if
  switch i32 %.325, label %for.body.if.endif.endif.endif [
    i32 -3, label %for.body.if.endif.if
    i32 -1, label %for.body.endif.thread
  ]

for.body.if.if.if:                                ; preds = %for.body.if.if
  %.351 = sext i32 %.350 to i64
  %.352 = call ptr @PyBytes_FromStringAndSize(ptr %.348, i64 %.351)
  %.353 = load { ptr, i32, ptr, ptr, i32 }, ptr %.326.le, align 8
  %.354 = extractvalue { ptr, i32, ptr, ptr, i32 } %.353, 2
  %.356 = extractvalue { ptr, i32, ptr, ptr, i32 } %.353, 3
  %.358 = call ptr %.356(ptr %.354)
  %.359 = icmp eq ptr %.358, null
  br i1 %.359, label %for.body.if.if.if.if, label %for.body.if.if.if.endif, !prof !0

for.body.if.if.else:                              ; preds = %for.body.if.if
  %.372 = extractvalue { ptr, i32, ptr, ptr, i32 } %.343, 2
  %.373 = call ptr @numba_unpickle(ptr %.348, i32 %.350, ptr %.372)
  br label %for.body.if.if.endif

for.body.if.if.endif:                             ; preds = %for.body.if.if.if.endif, %for.body.if.if.else
  %.375 = phi ptr [ %.363, %for.body.if.if.if.endif ], [ %.373, %for.body.if.if.else ]
  %.376.not = icmp eq ptr %.375, null
  br i1 %.376.not, label %for.body.endif.thread, label %for.body.if.if.endif.if, !prof !0

for.body.if.if.if.if:                             ; preds = %for.body.if.if.if
  call void @PyErr_SetString(ptr nonnull @PyExc_RuntimeError, ptr nonnull @".const.Error creating Python tuple from runtime exception arguments.9")
  br label %common.ret

for.body.if.if.if.endif:                          ; preds = %for.body.if.if.if
  %.363 = call ptr @numba_runtime_build_excinfo_struct(ptr %.352, ptr nonnull %.358)
  call void @NRT_Free(ptr nonnull %.326.le)
  br label %for.body.if.if.endif

for.body.if.if.endif.if:                          ; preds = %for.body.if.if.endif
  call void @numba_do_raise(ptr nonnull %.375)
  br label %for.body.endif.thread

for.body.if.endif.if:                             ; preds = %for.body.if.endif
  call void @PyErr_SetNone(ptr nonnull @PyExc_StopIteration)
  br label %for.body.endif.thread

for.body.if.endif.endif.endif:                    ; preds = %for.body.if.endif
  call void @PyErr_SetString(ptr nonnull @PyExc_SystemError, ptr nonnull @".const.unknown error when calling native function.10")
  br label %for.body.endif.thread

.continue:                                        ; preds = %for.body
  %scevgep = getelementptr i8, ptr %lsr.iv, i64 %.22
  %scevgep9 = getelementptr i8, ptr %lsr.iv8, i64 %.24
  %scevgep11 = getelementptr i8, ptr %lsr.iv10, i64 %.25
  %scevgep13 = getelementptr i8, ptr %lsr.iv12, i64 %.27
  %scevgep15 = getelementptr i8, ptr %lsr.iv14, i64 %.28
  %scevgep17 = getelementptr i8, ptr %lsr.iv16, i64 %.29
  %scevgep19 = getelementptr i8, ptr %lsr.iv18, i64 %.30
  %scevgep21 = getelementptr i8, ptr %lsr.iv20, i64 %.31
  %scevgep23 = getelementptr i8, ptr %lsr.iv22, i64 %.33
  %scevgep25 = getelementptr i8, ptr %lsr.iv24, i64 %.35
  %scevgep27 = getelementptr i8, ptr %lsr.iv26, i64 %.36
  %scevgep29 = getelementptr i8, ptr %lsr.iv28, i64 %.39
  %scevgep31 = getelementptr i8, ptr %lsr.iv30, i64 %.42
  %scevgep33 = getelementptr i8, ptr %lsr.iv32, i64 %.44
  %scevgep35 = getelementptr i8, ptr %lsr.iv34, i64 %.45
  %lsr.iv.next = add i64 %lsr.iv36, -1
  %exitcond.not = icmp eq i64 %lsr.iv.next, 0
  br i1 %exitcond.not, label %common.ret, label %for.body
}

define linkonce_odr range(i32 -1, -2) i32 @_ZN13_3cdynamic_3e35__numba_parfor_gufunc_0x24b56214910B3v24B126c8tJTC_2fWQAliW1xhDEoY6EEMEUOEMISPGsAQMVj4QniQ4IXKQEMXwoMGLoQDDVsQR1NHAS2hQ9XgStYwaUTI24JtBVoBDXtb9MCvVgdJqdcC7QJGJNxz8IQPcQgAE5ArrayIyLi1E1C7mutable7alignedEb5ArrayIdLi1E1C7mutable7alignedEddd23Literal_5bint_5d_280_295ArrayIdLi1E1C7mutable7alignedE5ArrayI10complex128Li1E1C7mutable7alignedEx5ArrayI10complex128Li2E1C7mutable7alignedE5ArrayIdLi2E1C7mutable7alignedE5ArrayIdLi1E1C7mutable7alignedEx5ArrayIdLi1E1C7mutable7alignedE(ptr noalias writeonly captures(none) %retptr, ptr noalias writeonly captures(none) %excinfo, ptr readnone captures(none) %arg.sched.0, ptr readnone captures(none) %arg.sched.1, i64 %arg.sched.2, i64 %arg.sched.3, ptr readonly captures(none) %arg.sched.4, i64 %arg.sched.5.0, i64 %arg.sched.6.0, i8 %arg._corridor__on_41, ptr %arg.T__target.0, ptr readnone captures(none) %arg.T__target.1, i64 %arg.T__target.2, i64 %arg.T__target.3, ptr readonly captures(none) %arg.T__target.4, i64 %arg.T__target.5.0, i64 %arg.T__target.6.0, double %arg.corridor__wl__max, double %arg.corridor__wl__min, double %arg.index__corridor, i64 %arg.index__seed, ptr %arg.k0__arr.0, ptr readnone captures(none) %arg.k0__arr.1, i64 %arg.k0__arr.2, i64 %arg.k0__arr.3, ptr readonly captures(none) %arg.k0__arr.4, i64 %arg.k0__arr.5.0, i64 %arg.k0__arr.6.0, ptr %arg.nSub__arr.0, ptr readnone captures(none) %arg.nSub__arr.1, i64 %arg.nSub__arr.2, i64 %arg.nSub__arr.3, ptr readonly captures(none) %arg.nSub__arr.4, i64 %arg.nSub__arr.5.0, i64 %arg.nSub__arr.6.0, i64 %arg.n__layers, ptr %arg.n__layers__flattened.0, ptr readnone captures(none) %arg.n__layers__flattened.1, i64 %arg.n__layers__flattened.2, i64 %arg.n__layers__flattened.3, ptr readonly captures(none) %arg.n__layers__flattened.4, i64 %arg.n__layers__flattened.5.0, i64 %arg.n__layers__flattened.5.1, i64 %arg.n__layers__flattened.6.0, i64 %arg.n__layers__flattened.6.1, ptr %arg.sim__thick__batch.0, ptr readnone captures(none) %arg.sim__thick__batch.1, i64 %arg.sim__thick__batch.2, i64 %arg.sim__thick__batch.3, ptr readonly captures(none) %arg.sim__thick__batch.4, i64 %arg.sim__thick__batch.5.0, i64 %arg.sim__thick__batch.5.1, i64 %arg.sim__thick__batch.6.0, i64 %arg.sim__thick__batch.6.1, ptr %arg.wls.0, ptr readnone captures(none) %arg.wls.1, i64 %arg.wls.2, i64 %arg.wls.3, ptr readonly captures(none) %arg.wls.4, i64 %arg.wls.5.0, i64 %arg.wls.6.0, i64 %arg.wls__size0_4, ptr %arg.rmse__arr.0, ptr readnone captures(none) %arg.rmse__arr.1, i64 %arg.rmse__arr.2, i64 %arg.rmse__arr.3, ptr writeonly captures(none) %arg.rmse__arr.4, i64 %arg.rmse__arr.5.0, i64 %arg.rmse__arr.6.0) local_unnamed_addr {
entry:
  %.703 = alloca double, align 8
  %excinfo.2 = alloca ptr, align 8
  %.742 = alloca double, align 8
  %excinfo.3 = alloca ptr, align 8
  %.835 = alloca double, align 8
  %excinfo.4 = alloca ptr, align 8
  %.874 = alloca double, align 8
  %excinfo.5 = alloca ptr, align 8
  %.1749 = alloca [3 x double], align 8
  %excinfo.6 = alloca ptr, align 8
  call void @llvm.memset.p0.i64(ptr noundef nonnull align 8 dereferenceable(24) %.1749, i8 0, i64 24, i1 false)
  store ptr null, ptr %excinfo.6, align 8
  tail call void @NRT_incref(ptr %arg.T__target.0)
  tail call void @NRT_incref(ptr %arg.k0__arr.0)
  tail call void @NRT_incref(ptr %arg.nSub__arr.0)
  tail call void @NRT_incref(ptr %arg.n__layers__flattened.0)
  tail call void @NRT_incref(ptr %arg.sim__thick__batch.0)
  tail call void @NRT_incref(ptr %arg.wls.0)
  tail call void @NRT_incref(ptr %arg.rmse__arr.0)
  %.194 = load i64, ptr %arg.sched.4, align 8
  %.232 = getelementptr i8, ptr %arg.sched.4, i64 8
  %.233 = load i64, ptr %.232, align 8
  %reass.sub = sub i64 %.233, %.194
  %.324 = add i64 %reass.sub, 1
  %.15.i = icmp slt i64 %arg.n__layers, 0
  br i1 %.15.i, label %B0.endif.endif.if.if, label %B0.endif.endif.i, !prof !0

B0.endif.endif.i:                                 ; preds = %entry
  %const = bitcast i64 576460752303423480 to i64
  %const_mat = add i64 %const, 7
  %.31.i = icmp samesign ugt i64 %arg.n__layers, %const_mat
  br i1 %.31.i, label %B0.endif.endif.if.if, label %B0.endif.endif.endif.i, !prof !0

B0.endif.endif.endif.i:                           ; preds = %B0.endif.endif.i
  %.30.i = shl i64 %arg.n__layers, 4
  %.7.i.i.i = tail call ptr @NRT_MemInfo_alloc_aligned(i64 %.30.i, i32 32), !noalias !40
  %.8.i.i.i = icmp eq ptr %.7.i.i.i, null
  br i1 %.8.i.i.i, label %B0.endif.endif.if.if, label %B0.endif.endif.endif, !prof !0

B112:                                             ; preds = %B112.lr.ph, %B1365
  %.541841881 = phi i64 [ %.324, %B112.lr.ph ], [ %.551, %B1365 ]
  %.548846880 = phi i64 [ %.194, %B112.lr.ph ], [ %.555, %B1365 ]
  %0 = icmp eq i8 %arg._corridor__on_41, 0
  %.551 = add nsw i64 %.541841881, -1
  %.555 = add i64 %.548846880, 1
  %.625 = mul i64 %.548846880, %arg.sim__thick__batch.5.1
  %.627 = getelementptr double, ptr %arg.sim__thick__batch.4, i64 %.625
  tail call void @NRT_incref(ptr %arg.sim__thick__batch.0)
  br i1 %0, label %B439.endif, label %B389

B389:                                             ; preds = %B112
  %.708 = call i32 @_ZN6certus7physics17certus_strat_math20_seeded_noise_sampleB3v25B76c8tJTIeFIjxB2IKSgI4CrvQCk0Z4yRYcWsCAgXrKFt1X1eogKfVaTWDAFsEMQEpRYBFNAA_3d_3dE23Literal_5bint_5d_280_2923Literal_5bint_5d_280_29y23Literal_5bint_5d_280_2927Literal_5bbool_5d_28True_29(ptr nonnull %.703, ptr nonnull %excinfo.2, i64 %arg.index__seed, i64 0, i64 %.548846880, i64 0, i8 1)
  %.718 = load double, ptr %.703, align 8
  switch i32 %.708, label %B389.if.if [
    i32 -2, label %B389.endif
    i32 0, label %B389.endif
  ], !prof !50

B831:                                             ; preds = %B831.preheader, %B1123.endif
  %lsr.iv81 = phi ptr [ %scevgep82, %B1123.endif ], [ %arg.n__layers__flattened.4, %B831.preheader ]
  %lsr.iv = phi ptr [ %scevgep65, %B1123.endif ], [ %scevgep64, %B831.preheader ]
  %mse_sum.2.1834 = phi double [ %.2056, %B1123.endif ], [ 0.000000e+00, %B831.preheader ]
  %.1062822832 = phi i64 [ %.1069, %B1123.endif ], [ 0, %B831.preheader ]
  %1 = icmp eq i8 %arg._corridor__on_41, 0
  %.1069 = add nuw nsw i64 %.1062822832, 1
  %.1142 = mul i64 %.1062822832, %arg.n__layers__flattened.5.1
  %.1144 = getelementptr { double, double }, ptr %arg.n__layers__flattened.4, i64 %.1142
  tail call void @NRT_incref(ptr %arg.n__layers__flattened.0)
  tail call void @NRT_incref(ptr %arg.n__layers__flattened.0)
  br i1 %1, label %B1123, label %B837

B837:                                             ; preds = %B831
  %2 = icmp eq i64 %arg.n__layers, 0
  tail call void @NRT_decref(ptr %arg.n__layers__flattened.0)
  %3 = getelementptr double, ptr %arg.wls.4, i64 %.1062822832
  %.1240 = load double, ptr %3, align 8
  %.1246 = fmul fast double %.1240, 2.000000e+00
  %.1254 = fsub fast double %.1246, %32
  %.reass = fmul fast double %.1254, %b_l.2.1
  %.1273.reass = fmul fast double %.1254, %b_h.2.1
  %.1279 = fadd fast double %.1273.reass, %a_h.2.1
  %.1295 = fadd fast double %.reass, %a_l.2.1
  br i1 %2, label %B1099, label %B1043.else.if.preheader

B1043.else.if.preheader:                          ; preds = %B837
  br i1 %brmerge, label %B1043.else.if.preheader51, label %vector.ph

vector.ph:                                        ; preds = %B1043.else.if.preheader
  %broadcast.splatinsert = insertelement <4 x double> poison, double %.1279, i64 0
  %broadcast.splat = shufflevector <4 x double> %broadcast.splatinsert, <4 x double> poison, <4 x i32> zeroinitializer
  %broadcast.splatinsert44 = insertelement <4 x double> poison, double %.1295, i64 0
  %broadcast.splat45 = shufflevector <4 x double> %broadcast.splatinsert44, <4 x double> poison, <4 x i32> zeroinitializer
  br label %vector.body

vector.body:                                      ; preds = %vector.body, %vector.ph
  %lsr.iv66 = phi i64 [ %lsr.iv.next, %vector.body ], [ 0, %vector.ph ]
  %vec.ind = phi <4 x i64> [ %vec.ind.next, %vector.body ], [ <i64 0, i64 1, i64 2, i64 3>, %vector.ph ]
  %scevgep68 = getelementptr i8, ptr %lsr.iv, i64 %lsr.iv66
  %scevgep69 = getelementptr i8, ptr %scevgep68, i64 -64
  %wide.vec = load <8 x double>, ptr %scevgep69, align 8, !alias.scope !51
  %strided.vec = shufflevector <8 x double> %wide.vec, <8 x double> poison, <4 x i32> <i32 0, i32 2, i32 4, i32 6>
  %strided.vec46 = shufflevector <8 x double> %wide.vec, <8 x double> poison, <4 x i32> <i32 1, i32 3, i32 5, i32 7>
  %wide.vec47 = load <8 x double>, ptr %scevgep68, align 8, !alias.scope !51
  %strided.vec48 = shufflevector <8 x double> %wide.vec47, <8 x double> poison, <4 x i32> <i32 0, i32 2, i32 4, i32 6>
  %strided.vec49 = shufflevector <8 x double> %wide.vec47, <8 x double> poison, <4 x i32> <i32 1, i32 3, i32 5, i32 7>
  %4 = and <4 x i64> %vec.ind, splat (i64 1)
  %5 = icmp eq <4 x i64> %4, zeroinitializer
  %6 = select <4 x i1> %5, <4 x double> %broadcast.splat, <4 x double> %broadcast.splat45
  %7 = fadd fast <4 x double> %6, %strided.vec
  %8 = fadd fast <4 x double> %6, %strided.vec48
  %interleaved.vec = shufflevector <4 x double> %7, <4 x double> %strided.vec46, <8 x i32> <i32 0, i32 4, i32 1, i32 5, i32 2, i32 6, i32 3, i32 7>
  %sunkaddr = getelementptr i8, ptr %.6.i.i, i64 %lsr.iv66
  store <8 x double> %interleaved.vec, ptr %sunkaddr, align 8, !alias.scope !54, !noalias !51
  %interleaved.vec50 = shufflevector <4 x double> %8, <4 x double> %strided.vec49, <8 x i32> <i32 0, i32 4, i32 1, i32 5, i32 2, i32 6, i32 3, i32 7>
  %sunkaddr99 = getelementptr i8, ptr %.6.i.i, i64 %lsr.iv66
  %sunkaddr100 = getelementptr i8, ptr %sunkaddr99, i64 64
  store <8 x double> %interleaved.vec50, ptr %sunkaddr100, align 8, !alias.scope !54, !noalias !51
  %vec.ind.next = add <4 x i64> %vec.ind, splat (i64 8)
  %lsr.iv.next = add nuw nsw i64 %lsr.iv66, 128
  %9 = icmp eq i64 %29, %lsr.iv.next
  br i1 %9, label %middle.block, label %vector.body, !llvm.loop !56

middle.block:                                     ; preds = %vector.body
  %10 = icmp eq i64 %arg.n__layers, %n.vec
  br i1 %10, label %B1099, label %B1043.else.if.preheader51

B1043.else.if.preheader51:                        ; preds = %middle.block, %B1043.else.if.preheader
  %.1398816818.ph = phi i64 [ %n.vec, %middle.block ], [ 0, %B1043.else.if.preheader ]
  %11 = icmp eq i64 %xtraiter, 0
  br i1 %11, label %B1043.else.if.prol.loopexit, label %B1043.else.if.prol.preheader

B1043.else.if.prol.preheader:                     ; preds = %B1043.else.if.preheader51
  %12 = shl nuw nsw i64 %.1398816818.ph, 4
  %scevgep75 = getelementptr i8, ptr %scevgep74, i64 %12
  %scevgep83 = getelementptr i8, ptr %lsr.iv81, i64 %12
  br label %B1043.else.if.prol

B1043.else.if.prol:                               ; preds = %B1043.else.if.prol, %B1043.else.if.prol.preheader
  %lsr.iv76 = phi i64 [ 0, %B1043.else.if.prol.preheader ], [ %lsr.iv.next77, %B1043.else.if.prol ]
  %.1398816818.prol = phi i64 [ %.1398816818.ph, %B1043.else.if.prol.preheader ], [ %.1405.prol, %B1043.else.if.prol ]
  %.1405.prol = add nuw nsw i64 %.1398816818.prol, 1
  %scevgep84 = getelementptr i8, ptr %scevgep83, i64 %lsr.iv76
  %.1471.prol = load double, ptr %scevgep84, align 8
  %scevgep85 = getelementptr i8, ptr %scevgep84, i64 8
  %.1473.prol = load double, ptr %scevgep85, align 8
  %13 = and i64 %.1398816818.prol, 1
  %.1524.prol = icmp eq i64 %13, 0
  %spec.select803.prol = select i1 %.1524.prol, double %.1279, double %.1295
  %.1585.prol = fadd fast double %spec.select803.prol, %.1471.prol
  %scevgep79 = getelementptr i8, ptr %scevgep75, i64 %lsr.iv76
  %scevgep80 = getelementptr i8, ptr %scevgep79, i64 -8
  store double %.1585.prol, ptr %scevgep80, align 8
  store double %.1473.prol, ptr %scevgep79, align 8
  %lsr.iv.next77 = add nuw nsw i64 %lsr.iv76, 16
  %prol.iter.cmp.not = icmp eq i64 %30, %lsr.iv.next77
  br i1 %prol.iter.cmp.not, label %B1043.else.if.prol.loopexit, label %B1043.else.if.prol, !llvm.loop !57

B1043.else.if.prol.loopexit:                      ; preds = %B1043.else.if.prol, %B1043.else.if.preheader51
  %.1398816818.unr = phi i64 [ %.1398816818.ph, %B1043.else.if.preheader51 ], [ %.1405.prol, %B1043.else.if.prol ]
  %14 = sub nsw i64 %.1398816818.ph, %arg.n__layers
  %15 = icmp ugt i64 %14, -4
  br i1 %15, label %B1099, label %B1043.else.if.preheader51.new

B1043.else.if.preheader51.new:                    ; preds = %B1043.else.if.prol.loopexit
  %16 = and i64 %.1398816818.unr, 1
  %.1524 = icmp eq i64 %16, 0
  %spec.select803 = select i1 %.1524, double %.1279, double %.1295
  %spec.select803.1 = select i1 %.1524, double %.1295, double %.1279
  %17 = shl nuw nsw i64 %.1398816818.unr, 4
  %18 = add i64 %34, %.1398816818.unr
  br label %B1043.else.if

B1099:                                            ; preds = %B1043.else.if, %B1043.else.if.prol.loopexit, %middle.block, %B837
  tail call void @NRT_incref(ptr nonnull %.7.i.i.i)
  tail call void @NRT_decref(ptr %arg.n__layers__flattened.0)
  br label %B1123

B1123:                                            ; preds = %B1099, %B831
  %n_row.sroa.0.2 = phi ptr [ null, %B1099 ], [ %arg.n__layers__flattened.0, %B831 ]
  %n_row.2.sroa.60.2 = phi i64 [ 16, %B1099 ], [ %arg.n__layers__flattened.6.1, %B831 ]
  %n_row.2.sroa.50.2 = phi i64 [ %arg.n__layers, %B1099 ], [ %arg.n__layers__flattened.5.1, %B831 ]
  %n_row.2.sroa.40.2 = phi ptr [ %.6.i.i, %B1099 ], [ %.1144, %B831 ]
  %n_row.2.sroa.30.2 = phi i64 [ 16, %B1099 ], [ %arg.n__layers__flattened.3, %B831 ]
  %n_row.2.sroa.10.2 = phi ptr [ null, %B1099 ], [ %arg.n__layers__flattened.1, %B831 ]
  %n_row.2.sroa.0.2 = phi ptr [ %.7.i.i.i, %B1099 ], [ %arg.n__layers__flattened.0, %B831 ]
  tail call void @NRT_decref(ptr %n_row.sroa.0.2)
  %19 = getelementptr double, ptr %arg.k0__arr.4, i64 %.1062822832
  %.1700 = load double, ptr %19, align 8
  %20 = getelementptr { double, double }, ptr %arg.nSub__arr.4, i64 %.1062822832
  %.1735 = load double, ptr %20, align 8
  %.1736 = getelementptr inbounds nuw i8, ptr %20, i64 8
  %.1737 = load double, ptr %.1736, align 8
  call void @llvm.memset.p0.i64(ptr noundef nonnull align 8 dereferenceable(24) %.1749, i8 0, i64 24, i1 false)
  %.1757 = call i32 @_ZN6certus7physics17certus_tmm_matrix33compute_TMM_single_point_k0_exactB3v10B76c8tJTIeFIjxB2IKSgI4CrvQCk0Z4yRYcWsCAgXrKFt1X1eogKfVaTWDAFsEMQEpRYBFNAA_3d_3dEd5ArrayIdLi1E1C7mutable7alignedE5ArrayI10complex128Li1E1C7mutable7alignedE10complex128(ptr nonnull %.1749, ptr nonnull %excinfo.6, double %.1700, ptr %arg.sim__thick__batch.0, ptr %arg.sim__thick__batch.1, i64 %arg.sim__thick__batch.5.1, i64 %arg.sim__thick__batch.3, ptr %.627, i64 %arg.sim__thick__batch.5.1, i64 %arg.sim__thick__batch.6.1, ptr %n_row.2.sroa.0.2, ptr %n_row.2.sroa.10.2, i64 %n_row.2.sroa.50.2, i64 %n_row.2.sroa.30.2, ptr %n_row.2.sroa.40.2, i64 %n_row.2.sroa.50.2, i64 %n_row.2.sroa.60.2, double %.1735, double %.1737)
  %cond8 = icmp eq i32 %.1757, 0
  br i1 %cond8, label %B1123.endif, label %B1123.if.if, !prof !24

B1365.loopexit:                                   ; preds = %B1123.endif
  %21 = fmul fast double %.2056, %33
  %22 = tail call fast double @llvm.sqrt.f64(double %21)
  br label %B1365

B1365:                                            ; preds = %B439.endif, %B1365.loopexit
  %mse_sum.2.1.lcssa = phi double [ 0.000000e+00, %B439.endif ], [ %22, %B1365.loopexit ]
  tail call void @NRT_decref(ptr %arg.sim__thick__batch.0)
  %.2167 = getelementptr double, ptr %arg.rmse__arr.4, i64 %.548846880
  store double %mse_sum.2.1.lcssa, ptr %.2167, align 8
  %.542 = icmp sgt i64 %.541841881, 1
  br i1 %.542, label %B112, label %B1564

common.ret:                                       ; preds = %B1123.if.if, %B389.endif.endif.endif.if.if, %B389.endif.endif.if.if, %B389.endif.if.if, %B389.if.if, %B0.endif.endif.if.if, %B1564
  %common.ret.op = phi i32 [ 0, %B1564 ], [ 1, %B0.endif.endif.if.if ], [ %.708, %B389.if.if ], [ %.747, %B389.endif.if.if ], [ %.840, %B389.endif.endif.if.if ], [ %.879, %B389.endif.endif.endif.if.if ], [ 1, %B1123.if.if ]
  ret i32 %common.ret.op

B1564:                                            ; preds = %B1365, %B0.endif.endif.endif
  tail call void @NRT_decref(ptr %arg.wls.0)
  tail call void @NRT_decref(ptr %arg.sim__thick__batch.0)
  tail call void @NRT_decref(ptr %arg.rmse__arr.0)
  tail call void @NRT_decref(ptr nonnull %.7.i.i.i)
  tail call void @NRT_decref(ptr %arg.n__layers__flattened.0)
  tail call void @NRT_decref(ptr %arg.nSub__arr.0)
  tail call void @NRT_decref(ptr %arg.k0__arr.0)
  tail call void @NRT_decref(ptr %arg.T__target.0)
  store ptr null, ptr %retptr, align 8
  br label %common.ret

B0.endif.endif.endif:                             ; preds = %B0.endif.endif.endif.i
  %const97 = bitcast i64 9223372036854775680 to i64
  %.5.i.i = getelementptr i8, ptr %.7.i.i.i, i64 24
  %.6.i.i = load ptr, ptr %.5.i.i, align 8, !noalias !59
  %const_mat98 = add i64 %const97, 127
  %.542875937 = icmp ult i64 %reass.sub, %const_mat98
  br i1 %.542875937, label %B112.lr.ph, label %B1564

B112.lr.ph:                                       ; preds = %B0.endif.endif.endif
  %.388 = fsub fast double %arg.corridor__wl__max, %arg.corridor__wl__min
  %.2110 = sitofp i64 %arg.wls__size0_4 to double
  %scevgep = getelementptr i8, ptr %.6.i.i, i64 %.30.i
  %23 = add i64 %arg.wls__size0_4, 1152921504606846975
  %24 = mul i64 %23, %arg.n__layers__flattened.5.1
  %25 = add i64 %24, %arg.n__layers
  %26 = shl i64 %25, 4
  %scevgep43 = getelementptr i8, ptr %arg.n__layers__flattened.4, i64 %26
  %bound0 = icmp ult ptr %.6.i.i, %scevgep43
  %bound1 = icmp ult ptr %arg.n__layers__flattened.4, %scevgep
  %found.conflict = and i1 %bound0, %bound1
  %const_mat96 = add i64 %const, 8
  %.mask = and i64 %arg.n__layers__flattened.5.1, %const_mat96
  %stride.check = icmp ne i64 %.mask, 0
  %27 = or i1 %stride.check, %found.conflict
  %n.vec = and i64 %arg.n__layers, %const
  %xtraiter = and i64 %arg.n__layers, 3
  %scevgep64 = getelementptr i8, ptr %arg.n__layers__flattened.4, i64 64
  %28 = shl i64 %arg.n__layers__flattened.5.1, 4
  %29 = and i64 %.30.i, %const97
  %scevgep74 = getelementptr i8, ptr %.6.i.i, i64 8
  %30 = shl i64 %xtraiter, 4
  %.785 = fdiv fast double %arg.index__corridor, %.388
  %31 = icmp samesign ult i64 %arg.n__layers, 8
  %brmerge = select i1 %31, i1 true, i1 %27
  %32 = fadd fast double %arg.corridor__wl__max, %arg.corridor__wl__min
  %33 = fdiv fast double 1.000000e+00, %.2110
  %34 = sub i64 0, %arg.n__layers
  br label %B112

B0.endif.endif.if.if:                             ; preds = %B0.endif.endif.endif.i, %B0.endif.endif.i, %entry
  %excinfo.1.0.ph = phi ptr [ @.const.picklebuf.ba289d81f05c7020f3477c15734804df65abe209.13, %B0.endif.endif.endif.i ], [ @.const.picklebuf.58e14eccb507b1e0206981740223e685cb8c3c57.14, %B0.endif.endif.i ], [ @.const.picklebuf.331b8563bdb9dac81b38422273052c486fc1706b.15, %entry ]
  store ptr %excinfo.1.0.ph, ptr %excinfo, align 8
  br label %common.ret

B389.endif:                                       ; preds = %B389, %B389
  %.747 = call i32 @_ZN6certus7physics17certus_strat_math20_seeded_noise_sampleB3v26B76c8tJTIeFIjxB2IKSgI4CrvQCk0Z4yRYcWsCAgXrKFt1X1eogKfVaTWDAFsEMQEpRYBFNAA_3d_3dE23Literal_5bint_5d_280_2923Literal_5bint_5d_280_29y23Literal_5bint_5d_281_2927Literal_5bbool_5d_28True_29(ptr nonnull %.742, ptr nonnull %excinfo.3, i64 %arg.index__seed, i64 0, i64 %.548846880, i64 1, i8 1)
  switch i32 %.747, label %B389.endif.if.if [
    i32 -2, label %B389.endif.endif
    i32 0, label %B389.endif.endif
  ], !prof !50

B389.if.if:                                       ; preds = %B389
  store ptr null, ptr %excinfo, align 8
  br label %common.ret

B389.endif.endif:                                 ; preds = %B389.endif, %B389.endif
  %.757 = load double, ptr %.742, align 8
  %.774 = fmul fast double %.718, %arg.index__corridor
  %.795 = tail call fast double @llvm.fabs.f64(double %.718)
  %.805 = fsub fast double 1.000000e+00, %.795
  %.840 = call i32 @_ZN6certus7physics17certus_strat_math20_seeded_noise_sampleB3v27B76c8tJTIeFIjxB2IKSgI4CrvQCk0Z4yRYcWsCAgXrKFt1X1eogKfVaTWDAFsEMQEpRYBFNAA_3d_3dE23Literal_5bint_5d_280_2923Literal_5bint_5d_281_29y23Literal_5bint_5d_280_2927Literal_5bbool_5d_28True_29(ptr nonnull %.835, ptr nonnull %excinfo.4, i64 %arg.index__seed, i64 1, i64 %.548846880, i64 0, i8 1)
  %.850 = load double, ptr %.835, align 8
  switch i32 %.840, label %B389.endif.endif.if.if [
    i32 -2, label %B389.endif.endif.endif
    i32 0, label %B389.endif.endif.endif
  ], !prof !50

B389.endif.if.if:                                 ; preds = %B389.endif
  store ptr null, ptr %excinfo, align 8
  br label %common.ret

B389.endif.endif.endif:                           ; preds = %B389.endif.endif, %B389.endif.endif
  %.879 = call i32 @_ZN6certus7physics17certus_strat_math20_seeded_noise_sampleB3v28B76c8tJTIeFIjxB2IKSgI4CrvQCk0Z4yRYcWsCAgXrKFt1X1eogKfVaTWDAFsEMQEpRYBFNAA_3d_3dE23Literal_5bint_5d_280_2923Literal_5bint_5d_281_29y23Literal_5bint_5d_281_2927Literal_5bbool_5d_28True_29(ptr nonnull %.874, ptr nonnull %excinfo.5, i64 %arg.index__seed, i64 1, i64 %.548846880, i64 1, i8 1)
  switch i32 %.879, label %B389.endif.endif.endif.if.if [
    i32 -2, label %B389.endif.endif.endif.endif
    i32 0, label %B389.endif.endif.endif.endif
  ], !prof !50

B389.endif.endif.if.if:                           ; preds = %B389.endif.endif
  store ptr null, ptr %excinfo, align 8
  br label %common.ret

B389.endif.endif.endif.endif:                     ; preds = %B389.endif.endif.endif, %B389.endif.endif.endif
  %.889 = load double, ptr %.874, align 8
  %.906 = fmul fast double %.850, %arg.index__corridor
  %.927 = tail call fast double @llvm.fabs.f64(double %.850)
  %.937 = fsub fast double 1.000000e+00, %.927
  %.813 = fmul fast double %.805, %.785
  %35 = fmul fast double %.813, %.757
  %.945 = fmul fast double %.937, %.785
  %36 = fmul fast double %.945, %.889
  br label %B439.endif

B389.endif.endif.endif.if.if:                     ; preds = %B389.endif.endif.endif
  store ptr null, ptr %excinfo, align 8
  br label %common.ret

B439.endif:                                       ; preds = %B389.endif.endif.endif.endif, %B112
  %a_h.2.1 = phi double [ %.774, %B389.endif.endif.endif.endif ], [ 0.000000e+00, %B112 ]
  %b_h.2.1 = phi double [ %35, %B389.endif.endif.endif.endif ], [ 0.000000e+00, %B112 ]
  %a_l.2.1 = phi double [ %.906, %B389.endif.endif.endif.endif ], [ 0.000000e+00, %B112 ]
  %b_l.2.1 = phi double [ %36, %B389.endif.endif.endif.endif ], [ 0.000000e+00, %B112 ]
  %37 = icmp slt i64 %arg.wls__size0_4, 1
  br i1 %37, label %B1365, label %B831.preheader

B831.preheader:                                   ; preds = %B439.endif
  br label %B831

B1043.else.if:                                    ; preds = %B1043.else.if, %B1043.else.if.preheader51.new
  %lsr.iv49 = phi i64 [ %lsr.iv.next50, %B1043.else.if ], [ %18, %B1043.else.if.preheader51.new ]
  %lsr.iv89 = phi i64 [ %lsr.iv.next90, %B1043.else.if ], [ %17, %B1043.else.if.preheader51.new ]
  %scevgep108 = getelementptr i8, ptr %lsr.iv81, i64 %lsr.iv89
  %.1471 = load double, ptr %scevgep108, align 8
  %scevgep114 = getelementptr i8, ptr %scevgep108, i64 8
  %.1473 = load double, ptr %scevgep114, align 8
  %.1585 = fadd fast double %.1471, %spec.select803
  %sunkaddr101 = getelementptr i8, ptr %.6.i.i, i64 %lsr.iv89
  store double %.1585, ptr %sunkaddr101, align 8
  %sunkaddr102 = getelementptr i8, ptr %.6.i.i, i64 %lsr.iv89
  %sunkaddr103 = getelementptr i8, ptr %sunkaddr102, i64 8
  store double %.1473, ptr %sunkaddr103, align 8
  %scevgep86 = getelementptr i8, ptr %lsr.iv81, i64 %lsr.iv89
  %scevgep88 = getelementptr i8, ptr %scevgep86, i64 16
  %.1471.1 = load double, ptr %scevgep88, align 8
  %scevgep78 = getelementptr i8, ptr %lsr.iv81, i64 %lsr.iv89
  %scevgep81 = getelementptr i8, ptr %scevgep78, i64 24
  %.1473.1 = load double, ptr %scevgep81, align 8
  %.1585.1 = fadd fast double %.1471.1, %spec.select803.1
  %sunkaddr104 = getelementptr i8, ptr %.6.i.i, i64 %lsr.iv89
  %sunkaddr105 = getelementptr i8, ptr %sunkaddr104, i64 16
  store double %.1585.1, ptr %sunkaddr105, align 8
  %sunkaddr106 = getelementptr i8, ptr %.6.i.i, i64 %lsr.iv89
  %sunkaddr107 = getelementptr i8, ptr %sunkaddr106, i64 24
  store double %.1473.1, ptr %sunkaddr107, align 8
  %scevgep71 = getelementptr i8, ptr %lsr.iv81, i64 %lsr.iv89
  %scevgep72 = getelementptr i8, ptr %scevgep71, i64 32
  %.1471.2 = load double, ptr %scevgep72, align 8
  %scevgep92 = getelementptr i8, ptr %scevgep71, i64 40
  %.1473.2 = load double, ptr %scevgep92, align 8
  %.1585.2 = fadd fast double %.1471.2, %spec.select803
  %sunkaddr108 = getelementptr i8, ptr %.6.i.i, i64 %lsr.iv89
  %sunkaddr109 = getelementptr i8, ptr %sunkaddr108, i64 32
  store double %.1585.2, ptr %sunkaddr109, align 8
  %sunkaddr110 = getelementptr i8, ptr %.6.i.i, i64 %lsr.iv89
  %sunkaddr111 = getelementptr i8, ptr %sunkaddr110, i64 40
  store double %.1473.2, ptr %sunkaddr111, align 8
  %scevgep94 = getelementptr i8, ptr %lsr.iv81, i64 %lsr.iv89
  %scevgep95 = getelementptr i8, ptr %scevgep94, i64 48
  %.1471.3 = load double, ptr %scevgep95, align 8
  %scevgep73 = getelementptr i8, ptr %lsr.iv81, i64 %lsr.iv89
  %scevgep77 = getelementptr i8, ptr %scevgep73, i64 56
  %.1473.3 = load double, ptr %scevgep77, align 8
  %.1585.3 = fadd fast double %.1471.3, %spec.select803.1
  %sunkaddr112 = getelementptr i8, ptr %.6.i.i, i64 %lsr.iv89
  %sunkaddr113 = getelementptr i8, ptr %sunkaddr112, i64 48
  store double %.1585.3, ptr %sunkaddr113, align 8
  %sunkaddr114 = getelementptr i8, ptr %.6.i.i, i64 %lsr.iv89
  %sunkaddr115 = getelementptr i8, ptr %sunkaddr114, i64 56
  store double %.1473.3, ptr %sunkaddr115, align 8
  %lsr.iv.next90 = add i64 %lsr.iv89, 64
  %lsr.iv.next50 = add i64 %lsr.iv49, 4
  %exitcond.not.3 = icmp eq i64 %lsr.iv.next50, 0
  br i1 %exitcond.not.3, label %B1099, label %B1043.else.if, !llvm.loop !60

B1123.endif:                                      ; preds = %B1123
  %sunkaddr118 = getelementptr inbounds i8, ptr %.1749, i64 16
  %.1767.fca.2.load = load double, ptr %sunkaddr118, align 8
  %sunkaddr119 = getelementptr inbounds i8, ptr %.1749, i64 8
  %.1767.fca.1.load = load double, ptr %sunkaddr119, align 8
  tail call void @NRT_decref(ptr %n_row.2.sroa.0.2)
  %.1855 = load double, ptr %20, align 8
  %.1875 = fadd fast double %.1855, -1.000000e+00
  %.1881 = fadd fast double %.1855, 1.000000e+00
  %.1892 = fdiv fast double %.1875, %.1881
  %.1902 = fmul fast double %.1892, %.1892
  %.1910 = fsub fast double 1.000000e+00, %.1902
  %.1916 = fmul fast double %.1902, %.1767.fca.2.load
  %.1926 = fsub fast double 1.000000e+00, %.1916
  %.1938 = fcmp fast olt double %.1926, 0x3D719799812DEA11
  %.1967777 = fmul fast double %.1910, %.1767.fca.1.load
  %denom.2.2776 = select i1 %.1938, double 0x3D719799812DEA11, double %.1926
  %.1980 = fdiv fast double %.1967777, %denom.2.2776
  %38 = getelementptr double, ptr %arg.T__target.4, i64 %.1062822832
  %.2018 = load double, ptr %38, align 8
  %.2026 = fsub fast double %.1980, %.2018
  %.2048 = fmul fast double %.2026, %.2026
  %.2056 = fadd fast double %.2048, %mse_sum.2.1834
  %scevgep65 = getelementptr i8, ptr %lsr.iv, i64 %28
  %scevgep82 = getelementptr i8, ptr %lsr.iv81, i64 %28
  %exitcond929.not = icmp eq i64 %arg.wls__size0_4, %.1069
  br i1 %exitcond929.not, label %B1365.loopexit, label %B831

B1123.if.if:                                      ; preds = %B1123
  %.1758 = load ptr, ptr %excinfo.6, align 8
  store ptr %.1758, ptr %excinfo, align 8
  br label %common.ret
}

; Function Attrs: mustprogress nofree noinline norecurse nounwind willreturn memory(argmem: readwrite)
define linkonce_odr void @NRT_incref(ptr captures(address_is_null) %.1) local_unnamed_addr #5 {
.3:
  %.4 = icmp eq ptr %.1, null
  br i1 %.4, label %common.ret, label %.3.endif, !prof !0

common.ret:                                       ; preds = %.3.endif, %.3
  ret void

.3.endif:                                         ; preds = %.3
  %.4.i = atomicrmw add ptr %.1, i64 1 monotonic, align 8
  br label %common.ret
}

; Function Attrs: mustprogress nofree norecurse nosync nounwind willreturn memory(argmem: write)
define linkonce_odr noundef i32 @_ZN6certus7physics17certus_strat_math20_seeded_noise_sampleB3v25B76c8tJTIeFIjxB2IKSgI4CrvQCk0Z4yRYcWsCAgXrKFt1X1eogKfVaTWDAFsEMQEpRYBFNAA_3d_3dE23Literal_5bint_5d_280_2923Literal_5bint_5d_280_29y23Literal_5bint_5d_280_2927Literal_5bbool_5d_28True_29(ptr noalias writeonly captures(none) initializes((0, 8)) %retptr, ptr noalias readnone captures(none) %excinfo, i64 %arg.seed_base, i64 %arg.group_idx, i64 %arg.run_idx, i64 %arg.elem_idx, i8 %arg.gaussian) local_unnamed_addr #6 {
entry:
  %const = bitcast i64 2685821657736338717 to i64
  %0 = mul i64 %arg.run_idx, -4658895280553007687
  %.171 = add i64 %0, -4244837359508594100
  %.174 = lshr i64 %.171, 12
  %.175 = xor i64 %.174, %.171
  %.176 = shl i64 %.175, 25
  %.177 = xor i64 %.176, %.175
  %.178 = lshr i64 %.177, 27
  %.179 = xor i64 %.178, %.177
  %.180 = mul i64 %.179, %const
  %.181 = lshr i64 %.180, 11
  %.173.1 = add i64 %0, -7507901964676673313
  %.174.1 = lshr i64 %.173.1, 12
  %.175.1 = xor i64 %.174.1, %.173.1
  %.176.1 = shl i64 %.175.1, 25
  %.177.1 = xor i64 %.176.1, %.175.1
  %.178.1 = lshr i64 %.177.1, 27
  %.179.1 = xor i64 %.178.1, %.177.1
  %.180.1 = mul i64 %.179.1, %const
  %.181.1 = lshr i64 %.180.1, 11
  %1 = add nuw nsw i64 %.181.1, %.181
  %2 = uitofp nneg i64 %1 to double
  %.173.2 = add i64 %0, 7675777503864799090
  %.174.2 = lshr i64 %.173.2, 12
  %.175.2 = xor i64 %.174.2, %.173.2
  %.176.2 = shl i64 %.175.2, 25
  %.177.2 = xor i64 %.176.2, %.175.2
  %.178.2 = lshr i64 %.177.2, 27
  %.179.2 = xor i64 %.178.2, %.177.2
  %.180.2 = mul i64 %.179.2, %const
  %.181.2 = lshr i64 %.180.2, 11
  %.173.3 = add i64 %0, 4412712898696719877
  %.174.3 = lshr i64 %.173.3, 12
  %.175.3 = xor i64 %.174.3, %.173.3
  %.176.3 = shl i64 %.175.3, 25
  %.177.3 = xor i64 %.176.3, %.175.3
  %.178.3 = lshr i64 %.177.3, 27
  %.179.3 = xor i64 %.178.3, %.177.3
  %.180.3 = mul i64 %.179.3, %const
  %.181.3 = lshr i64 %.180.3, 11
  %.173.4 = add i64 %0, 1149648293528640664
  %.174.4 = lshr i64 %.173.4, 12
  %.175.4 = xor i64 %.174.4, %.173.4
  %.176.4 = shl i64 %.175.4, 25
  %.177.4 = xor i64 %.176.4, %.175.4
  %.178.4 = lshr i64 %.177.4, 27
  %.179.4 = xor i64 %.178.4, %.177.4
  %.180.4 = mul i64 %.179.4, %const
  %.181.4 = lshr i64 %.180.4, 11
  %.173.5 = add i64 %0, -2113416311639438549
  %.174.5 = lshr i64 %.173.5, 12
  %.175.5 = xor i64 %.174.5, %.173.5
  %.176.5 = shl i64 %.175.5, 25
  %.177.5 = xor i64 %.176.5, %.175.5
  %.178.5 = lshr i64 %.177.5, 27
  %.179.5 = xor i64 %.178.5, %.177.5
  %.180.5 = mul i64 %.179.5, %const
  %.181.5 = lshr i64 %.180.5, 11
  %.173.6 = add i64 %0, -5376480916807517762
  %.174.6 = lshr i64 %.173.6, 12
  %.175.6 = xor i64 %.174.6, %.173.6
  %.176.6 = shl i64 %.175.6, 25
  %.177.6 = xor i64 %.176.6, %.175.6
  %.178.6 = lshr i64 %.177.6, 27
  %.179.6 = xor i64 %.178.6, %.177.6
  %.180.6 = mul i64 %.179.6, %const
  %.181.6 = lshr i64 %.180.6, 11
  %.173.7 = add i64 %0, -8639545521975596975
  %.174.7 = lshr i64 %.173.7, 12
  %.175.7 = xor i64 %.174.7, %.173.7
  %.176.7 = shl i64 %.175.7, 25
  %.177.7 = xor i64 %.176.7, %.175.7
  %.178.7 = lshr i64 %.177.7, 27
  %.179.7 = xor i64 %.178.7, %.177.7
  %.180.7 = mul i64 %.179.7, %const
  %.181.7 = lshr i64 %.180.7, 11
  %.173.8 = add i64 %0, 6544133946565875428
  %.174.8 = lshr i64 %.173.8, 12
  %.175.8 = xor i64 %.174.8, %.173.8
  %.176.8 = shl i64 %.175.8, 25
  %.177.8 = xor i64 %.176.8, %.175.8
  %.178.8 = lshr i64 %.177.8, 27
  %.179.8 = xor i64 %.178.8, %.177.8
  %.180.8 = mul i64 %.179.8, %const
  %.181.8 = lshr i64 %.180.8, 11
  %.173.9 = add i64 %0, 3281069341397796215
  %.174.9 = lshr i64 %.173.9, 12
  %.175.9 = xor i64 %.174.9, %.173.9
  %.176.9 = shl i64 %.175.9, 25
  %.177.9 = xor i64 %.176.9, %.175.9
  %.178.9 = lshr i64 %.177.9, 27
  %.179.9 = xor i64 %.178.9, %.177.9
  %.180.9 = mul i64 %.179.9, %const
  %.181.9 = lshr i64 %.180.9, 11
  %.173.10 = add i64 %0, 18004736229717002
  %.174.10 = lshr i64 %.173.10, 12
  %.175.10 = xor i64 %.174.10, %.173.10
  %.176.10 = shl i64 %.175.10, 25
  %.177.10 = xor i64 %.176.10, %.175.10
  %.178.10 = lshr i64 %.177.10, 27
  %.179.10 = xor i64 %.178.10, %.177.10
  %.180.10 = mul i64 %.179.10, %const
  %.181.10 = lshr i64 %.180.10, 11
  %.173.11 = add i64 %0, -3245059868938362211
  %.174.11 = lshr i64 %.173.11, 12
  %.175.11 = xor i64 %.174.11, %.173.11
  %.176.11 = shl i64 %.175.11, 25
  %.177.11 = xor i64 %.176.11, %.175.11
  %.178.11 = lshr i64 %.177.11, 27
  %.179.11 = xor i64 %.178.11, %.177.11
  %.180.11 = mul i64 %.179.11, %const
  %.181.11 = lshr i64 %.180.11, 11
  %3 = add nuw nsw i64 %.181.3, %.181.2
  %4 = uitofp nneg i64 %3 to double
  %5 = add nuw nsw i64 %.181.5, %.181.4
  %6 = uitofp nneg i64 %5 to double
  %7 = add nuw nsw i64 %.181.7, %.181.6
  %8 = uitofp nneg i64 %7 to double
  %9 = add nuw nsw i64 %.181.9, %.181.8
  %10 = uitofp nneg i64 %9 to double
  %11 = add nuw nsw i64 %.181.11, %.181.10
  %12 = uitofp nneg i64 %11 to double
  %13 = fadd fast double %12, %10
  %14 = fadd fast double %13, %8
  %15 = fadd fast double %14, %6
  %16 = fadd fast double %15, %4
  %17 = fadd fast double %16, %2
  %18 = fmul fast double %17, 0x3C85555555555555
  %.202 = fadd fast double %18, -2.000000e+00
  %.214 = fcmp fast ogt double %.202, 1.000000e+00
  %..202 = select i1 %.214, double 1.000000e+00, double %.202
  %.inv = fcmp fast oge double %..202, -1.000000e+00
  %.202.sink47 = select nnan ninf i1 %.inv, double %..202, double -1.000000e+00
  store double %.202.sink47, ptr %retptr, align 8
  ret i32 0
}

define linkonce_odr range(i32 0, 2) i32 @_ZN6certus7physics17certus_tmm_matrix33compute_TMM_single_point_k0_exactB3v10B76c8tJTIeFIjxB2IKSgI4CrvQCk0Z4yRYcWsCAgXrKFt1X1eogKfVaTWDAFsEMQEpRYBFNAA_3d_3dEd5ArrayIdLi1E1C7mutable7alignedE5ArrayI10complex128Li1E1C7mutable7alignedE10complex128(ptr noalias writeonly captures(none) %retptr, ptr noalias writeonly captures(none) %excinfo, double %arg.k0, ptr %arg.thicknesses.0, ptr readnone captures(none) %arg.thicknesses.1, i64 %arg.thicknesses.2, i64 %arg.thicknesses.3, ptr readonly captures(none) %arg.thicknesses.4, i64 %arg.thicknesses.5.0, i64 %arg.thicknesses.6.0, ptr %arg.n_layers_complex.0, ptr readnone captures(none) %arg.n_layers_complex.1, i64 %arg.n_layers_complex.2, i64 %arg.n_layers_complex.3, ptr readonly captures(none) %arg.n_layers_complex.4, i64 %arg.n_layers_complex.5.0, i64 %arg.n_layers_complex.6.0, double %arg.n_sub.0, double %arg.n_sub.1) local_unnamed_addr {
B0.endif:
  %.1481 = alloca [2 x double], align 8
  %excinfo.26 = alloca ptr, align 8
  store ptr null, ptr %excinfo.26, align 8
  %.1527 = alloca [2 x double], align 8
  %excinfo.27 = alloca ptr, align 8
  store ptr null, ptr %excinfo.27, align 8
  tail call void @NRT_incref(ptr %arg.thicknesses.0)
  tail call void @NRT_incref(ptr %arg.n_layers_complex.0)
  %.2401169.not = icmp slt i64 %arg.thicknesses.5.0, 1
  br i1 %.2401169.not, label %B1006, label %B254.preheader

B254.preheader:                                   ; preds = %B0.endif
  %0 = fneg fast double %arg.k0
  %scevgep582 = getelementptr i8, ptr %arg.n_layers_complex.4, i64 8
  br label %B254

B254:                                             ; preds = %B576.endif.endif.endif.en...endif.2, %B254.preheader
  %lsr.iv = phi ptr [ %scevgep582, %B254.preheader ], [ %scevgep583, %B576.endif.endif.endif.en...endif.2 ]
  %Mb11.2.sroa.0.01187 = phi double [ 1.000000e+00, %B254.preheader ], [ %.1374, %B576.endif.endif.endif.en...endif.2 ]
  %Mb11.2.sroa.10.01186 = phi double [ 0.000000e+00, %B254.preheader ], [ %.1377, %B576.endif.endif.endif.en...endif.2 ]
  %Mb10.2.sroa.0.01185 = phi double [ 0.000000e+00, %B254.preheader ], [ %.1291, %B576.endif.endif.endif.en...endif.2 ]
  %Mb10.2.sroa.10.01184 = phi double [ 0.000000e+00, %B254.preheader ], [ %.1294, %B576.endif.endif.endif.en...endif.2 ]
  %Mb01.2.sroa.0.01183 = phi double [ 0.000000e+00, %B254.preheader ], [ %.1210, %B576.endif.endif.endif.en...endif.2 ]
  %Mb01.2.sroa.10.01182 = phi double [ 0.000000e+00, %B254.preheader ], [ %.1213, %B576.endif.endif.endif.en...endif.2 ]
  %Mb00.2.sroa.0.01181 = phi double [ 1.000000e+00, %B254.preheader ], [ %.1129, %B576.endif.endif.endif.en...endif.2 ]
  %Mb00.2.sroa.10.01180 = phi double [ 0.000000e+00, %B254.preheader ], [ %.1132, %B576.endif.endif.endif.en...endif.2 ]
  %M11.2.sroa.0.01179 = phi double [ 1.000000e+00, %B254.preheader ], [ %.1048, %B576.endif.endif.endif.en...endif.2 ]
  %M11.2.sroa.10.01178 = phi double [ 0.000000e+00, %B254.preheader ], [ %.1051, %B576.endif.endif.endif.en...endif.2 ]
  %M10.2.sroa.0.01177 = phi double [ 0.000000e+00, %B254.preheader ], [ %.967, %B576.endif.endif.endif.en...endif.2 ]
  %M10.2.sroa.10.01176 = phi double [ 0.000000e+00, %B254.preheader ], [ %.970, %B576.endif.endif.endif.en...endif.2 ]
  %M01.2.sroa.0.01175 = phi double [ 0.000000e+00, %B254.preheader ], [ %.886, %B576.endif.endif.endif.en...endif.2 ]
  %M01.2.sroa.10.01174 = phi double [ 0.000000e+00, %B254.preheader ], [ %.889, %B576.endif.endif.endif.en...endif.2 ]
  %M00.2.sroa.0.01173 = phi double [ 1.000000e+00, %B254.preheader ], [ %.805, %B576.endif.endif.endif.en...endif.2 ]
  %M00.2.sroa.10.01172 = phi double [ 0.000000e+00, %B254.preheader ], [ %.808, %B576.endif.endif.endif.en...endif.2 ]
  %.24611441170 = phi i64 [ 0, %B254.preheader ], [ %.253, %B576.endif.endif.endif.en...endif.2 ]
  %.253 = add nuw nsw i64 %.24611441170, 1
  %scevgep584 = getelementptr i8, ptr %lsr.iv, i64 -8
  %.312 = load double, ptr %scevgep584, align 8
  %.314 = load double, ptr %lsr.iv, align 8
  %.329 = fcmp fast ogt double %.314, 0.000000e+00
  %.411 = fneg fast double %.314
  %nc.2.sroa.11.1 = select nnan ninf i1 %.329, double %.411, double %.314
  %.46.i = fmul fast double %.312, %arg.k0
  %1 = shl i64 %.24611441170, 3
  %scevgep = getelementptr i8, ptr %arg.thicknesses.4, i64 %1
  %.486 = load double, ptr %scevgep, align 8
  %.46.i401 = fmul fast double %.46.i, %.486
  %2 = fmul fast double %.486, %0
  %.12.i = fmul fast double %2, %nc.2.sroa.11.1
  %.109.i.i = tail call double @llvm.cos.f64(double %.46.i401)
  %.111.i.i = tail call double @cosh(double %.12.i)
  %.112.i.i = fmul double %.111.i.i, %.109.i.i
  %.114.i.i = tail call double @llvm.sin.f64(double %.46.i401)
  %.118.i.i = tail call double @sinh(double %.12.i)
  %.121.i.i = fmul double %.114.i.i, %.118.i.i
  %.136.i.i = fmul double %.111.i.i, %.114.i.i
  %.70.i413 = fmul fast double %.118.i.i, %.109.i.i
  %.6.i.i = tail call fast double @_hypot(double %.312, double %nc.2.sroa.11.1), !noalias !61
  %.659 = fcmp fast ogt double %.6.i.i, 0x3D719799812DEA11
  br i1 %.659, label %B554, label %B576.endif.endif.endif.en...endif.2

B554:                                             ; preds = %B254
  %.45.i = tail call fast double @llvm.fabs.f64(double %.312)
  %.50.i = tail call fast double @llvm.fabs.f64(double %.314)
  %.56.i = fcmp fast ult double %.45.i, %.50.i
  br i1 %.56.i, label %B344.i, label %B154.i

B154.i:                                           ; preds = %B554
  %.59.i = fcmp fast oeq double %.312, 0.000000e+00
  br i1 %.59.i, label %B554.if.if, label %B192.endif.i

B344.i:                                           ; preds = %B554
  %.132.i = fcmp fast ult double %.50.i, %.45.i
  br i1 %.132.i, label %B576.endif.endif.endif.en...endif.2, label %B354.i

B354.i:                                           ; preds = %B344.i
  %.136.i = fcmp fast oeq double %.314, 0.000000e+00
  br i1 %.136.i, label %B554.if.if, label %B354.endif.i, !prof !0

B192.endif.i:                                     ; preds = %B154.i
  %.89.i = fdiv fast double %nc.2.sroa.11.1, %.312
  %.91.i = fmul fast double %.89.i, %nc.2.sroa.11.1
  %.93.i = fadd fast double %.91.i, %.312
  %.98.i = fcmp fast oeq double %.93.i, 0.000000e+00
  br i1 %.98.i, label %B554.if.if, label %B192.endif.endif.endif.i, !prof !0

B192.endif.endif.endif.i:                         ; preds = %B192.endif.i
  %.95.i = fmul fast double %.136.i.i, %.89.i
  %.97.i = fadd fast double %.95.i, %.70.i413
  %.105.i = fdiv fast double %.97.i, %.93.i
  %.107.i = fmul fast double %.70.i413, %.89.i
  %.109.i = fsub fast double %.136.i.i, %.107.i
  %.117.i = fdiv fast double %.109.i, %.93.i
  br label %B576.endif.endif.endif.en...endif.2

B354.endif.i:                                     ; preds = %B354.i
  %.143.i = fdiv fast double %.312, %nc.2.sroa.11.1
  %.145.i = fmul fast double %.143.i, %.312
  %.147.i = fadd fast double %.145.i, %nc.2.sroa.11.1
  %.152.i = fcmp fast oeq double %.147.i, 0.000000e+00
  br i1 %.152.i, label %B554.if.if, label %B354.endif.endif.endif.i, !prof !0

B354.endif.endif.endif.i:                         ; preds = %B354.endif.i
  %.149.i = fmul fast double %.70.i413, %.143.i
  %.151.i = fadd fast double %.149.i, %.136.i.i
  %.159.i = fdiv fast double %.151.i, %.147.i
  %.161.i = fmul fast double %.136.i.i, %.143.i
  %.163.i = fsub fast double %.161.i, %.70.i413
  %.171.i = fdiv fast double %.163.i, %.147.i
  br label %B576.endif.endif.endif.en...endif.2

B1006:                                            ; preds = %B576.endif.endif.endif.en...endif.2, %B0.endif
  %M00.2.sroa.10.0.lcssa = phi double [ 0.000000e+00, %B0.endif ], [ %.808, %B576.endif.endif.endif.en...endif.2 ]
  %M00.2.sroa.0.0.lcssa = phi double [ 1.000000e+00, %B0.endif ], [ %.805, %B576.endif.endif.endif.en...endif.2 ]
  %M01.2.sroa.10.0.lcssa = phi double [ 0.000000e+00, %B0.endif ], [ %.889, %B576.endif.endif.endif.en...endif.2 ]
  %M01.2.sroa.0.0.lcssa = phi double [ 0.000000e+00, %B0.endif ], [ %.886, %B576.endif.endif.endif.en...endif.2 ]
  %M10.2.sroa.10.0.lcssa = phi double [ 0.000000e+00, %B0.endif ], [ %.970, %B576.endif.endif.endif.en...endif.2 ]
  %M10.2.sroa.0.0.lcssa = phi double [ 0.000000e+00, %B0.endif ], [ %.967, %B576.endif.endif.endif.en...endif.2 ]
  %M11.2.sroa.10.0.lcssa = phi double [ 0.000000e+00, %B0.endif ], [ %.1051, %B576.endif.endif.endif.en...endif.2 ]
  %M11.2.sroa.0.0.lcssa = phi double [ 1.000000e+00, %B0.endif ], [ %.1048, %B576.endif.endif.endif.en...endif.2 ]
  %Mb00.2.sroa.10.0.lcssa = phi double [ 0.000000e+00, %B0.endif ], [ %.1132, %B576.endif.endif.endif.en...endif.2 ]
  %Mb00.2.sroa.0.0.lcssa = phi double [ 1.000000e+00, %B0.endif ], [ %.1129, %B576.endif.endif.endif.en...endif.2 ]
  %Mb01.2.sroa.10.0.lcssa = phi double [ 0.000000e+00, %B0.endif ], [ %.1213, %B576.endif.endif.endif.en...endif.2 ]
  %Mb01.2.sroa.0.0.lcssa = phi double [ 0.000000e+00, %B0.endif ], [ %.1210, %B576.endif.endif.endif.en...endif.2 ]
  %Mb10.2.sroa.10.0.lcssa = phi double [ 0.000000e+00, %B0.endif ], [ %.1294, %B576.endif.endif.endif.en...endif.2 ]
  %Mb10.2.sroa.0.0.lcssa = phi double [ 0.000000e+00, %B0.endif ], [ %.1291, %B576.endif.endif.endif.en...endif.2 ]
  %Mb11.2.sroa.10.0.lcssa = phi double [ 0.000000e+00, %B0.endif ], [ %.1377, %B576.endif.endif.endif.en...endif.2 ]
  %Mb11.2.sroa.0.0.lcssa = phi double [ 1.000000e+00, %B0.endif ], [ %.1374, %B576.endif.endif.endif.en...endif.2 ]
  tail call void @NRT_decref(ptr %arg.thicknesses.0)
  tail call void @NRT_decref(ptr %arg.n_layers_complex.0)
  call void @llvm.memset.p0.i64(ptr noundef nonnull align 8 dereferenceable(16) %.1481, i8 0, i64 16, i1 false)
  %.1485 = call i32 @_ZN6certus7physics14certus_opt_tmm22compute_RT_from_matrixB3v11B76c8tJTIeFIjxB2IKSgI4CrvQCk0Z4yRYcWsCAgXrKFt1X1eogKfVaTWDAFsEMQEpRYBFNAA_3d_3dE10complex12810complex12810complex12810complex12810complex12810complex128(ptr nonnull %.1481, ptr nonnull %excinfo.26, double %M00.2.sroa.0.0.lcssa, double %M00.2.sroa.10.0.lcssa, double %M01.2.sroa.0.0.lcssa, double %M01.2.sroa.10.0.lcssa, double %M10.2.sroa.0.0.lcssa, double %M10.2.sroa.10.0.lcssa, double %M11.2.sroa.0.0.lcssa, double %M11.2.sroa.10.0.lcssa, double 1.000000e+00, double 0.000000e+00, double %arg.n_sub.0, double %arg.n_sub.1)
  %.1495.fca.0.load = load double, ptr %.1481, align 8
  %sunkaddr = getelementptr inbounds nuw i8, ptr %.1481, i64 8
  %.1495.fca.1.load = load double, ptr %sunkaddr, align 8
  %cond395 = icmp eq i32 %.1485, 0
  br i1 %cond395, label %B1006.endif, label %B1006.if.if, !prof !24

common.ret:                                       ; preds = %B1006.endif.if.if, %B1006.endif.endif, %B1006.if.if, %B554.if.if
  %common.ret.op = phi i32 [ 1, %B1006.endif.if.if ], [ 0, %B1006.endif.endif ], [ 1, %B1006.if.if ], [ 1, %B554.if.if ]
  ret i32 %common.ret.op

B554.if.if:                                       ; preds = %B354.endif.i, %B192.endif.i, %B354.i, %B154.i
  %excinfo.8.2.ph = phi ptr [ @.const.picklebuf.b28008a0f88bad5ff0f0243e84dab90cab19b366, %B354.endif.i ], [ @.const.picklebuf.b28008a0f88bad5ff0f0243e84dab90cab19b366, %B354.i ], [ @.const.picklebuf.b28008a0f88bad5ff0f0243e84dab90cab19b366, %B192.endif.i ], [ @.const.picklebuf.b6e474b50ffce3a1cb8e957957228030e14ea2dc, %B154.i ]
  store ptr %excinfo.8.2.ph, ptr %excinfo, align 8
  br label %common.ret

B576.endif.endif.endif.en...endif.2:              ; preds = %B354.endif.endif.endif.i, %B192.endif.endif.endif.i, %B344.i, %B254
  %"$phi576.1.2.sroa.8.1" = phi double [ 0.000000e+00, %B254 ], [ 0x7FF8000000000000, %B344.i ], [ %.117.i, %B192.endif.endif.endif.i ], [ %.171.i, %B354.endif.endif.endif.i ]
  %"$phi576.1.2.sroa.0.1" = phi double [ 0.000000e+00, %B254 ], [ 0x7FF8000000000000, %B344.i ], [ %.105.i, %B192.endif.endif.endif.i ], [ %.159.i, %B354.endif.endif.endif.i ]
  %.46.i398 = fmul fast double %.70.i413, %.312
  %.52.i = fmul fast double %.136.i.i, %nc.2.sroa.11.1
  %.58.i399 = fmul fast double %.70.i413, %nc.2.sroa.11.1
  %.64.i = fmul fast double %.136.i.i, %.312
  %.70.i = fsub fast double %.46.i398, %.52.i
  %.80.i = fadd fast double %.58.i399, %.64.i
  %.46.i416 = fmul fast double %.112.i.i, %M00.2.sroa.0.01173
  %.52.i417 = fmul fast double %.121.i.i, %M00.2.sroa.10.01172
  %.58.i418 = fmul fast double %.112.i.i, %M00.2.sroa.10.01172
  %.64.i419 = fmul fast double %.121.i.i, %M00.2.sroa.0.01173
  %.70.i420 = fsub fast double %.46.i416, %.52.i417
  %.46.i423 = fmul fast double %"$phi576.1.2.sroa.0.1", %M10.2.sroa.0.01177
  %.52.i424 = fmul fast double %"$phi576.1.2.sroa.8.1", %M10.2.sroa.10.01176
  %.58.i425 = fmul fast double %"$phi576.1.2.sroa.0.1", %M10.2.sroa.10.01176
  %.64.i426 = fmul fast double %"$phi576.1.2.sroa.8.1", %M10.2.sroa.0.01177
  %.70.i427 = fsub fast double %.46.i423, %.52.i424
  %.805 = fadd fast double %.70.i427, %.70.i420
  %.80.i428 = fadd fast double %.58.i418, %.64.i419
  %.80.i421 = fadd fast double %.80.i428, %.64.i426
  %.808 = fadd fast double %.80.i421, %.58.i425
  %.46.i430 = fmul fast double %.112.i.i, %M01.2.sroa.0.01175
  %.52.i431 = fmul fast double %.121.i.i, %M01.2.sroa.10.01174
  %.58.i432 = fmul fast double %.112.i.i, %M01.2.sroa.10.01174
  %.64.i433 = fmul fast double %.121.i.i, %M01.2.sroa.0.01175
  %.70.i434 = fsub fast double %.46.i430, %.52.i431
  %.46.i437 = fmul fast double %"$phi576.1.2.sroa.0.1", %M11.2.sroa.0.01179
  %.52.i438 = fmul fast double %"$phi576.1.2.sroa.8.1", %M11.2.sroa.10.01178
  %.58.i439 = fmul fast double %"$phi576.1.2.sroa.0.1", %M11.2.sroa.10.01178
  %.64.i440 = fmul fast double %"$phi576.1.2.sroa.8.1", %M11.2.sroa.0.01179
  %.70.i441 = fsub fast double %.46.i437, %.52.i438
  %.886 = fadd fast double %.70.i441, %.70.i434
  %.80.i442 = fadd fast double %.58.i432, %.64.i433
  %.80.i435 = fadd fast double %.80.i442, %.64.i440
  %.889 = fadd fast double %.80.i435, %.58.i439
  %.46.i444 = fmul fast double %.70.i, %M00.2.sroa.0.01173
  %.52.i445 = fmul fast double %.80.i, %M00.2.sroa.10.01172
  %.58.i446 = fmul fast double %.70.i, %M00.2.sroa.10.01172
  %.64.i447 = fmul fast double %.80.i, %M00.2.sroa.0.01173
  %.70.i448 = fsub fast double %.46.i444, %.52.i445
  %.46.i451 = fmul fast double %.112.i.i, %M10.2.sroa.0.01177
  %.52.i452 = fmul fast double %.121.i.i, %M10.2.sroa.10.01176
  %.58.i453 = fmul fast double %.112.i.i, %M10.2.sroa.10.01176
  %.64.i454 = fmul fast double %.121.i.i, %M10.2.sroa.0.01177
  %.70.i455 = fsub fast double %.46.i451, %.52.i452
  %.967 = fadd fast double %.70.i448, %.70.i455
  %.80.i449 = fadd fast double %.58.i453, %.64.i454
  %.80.i456 = fadd fast double %.80.i449, %.64.i447
  %.970 = fadd fast double %.80.i456, %.58.i446
  %.46.i458 = fmul fast double %.70.i, %M01.2.sroa.0.01175
  %.52.i459 = fmul fast double %.80.i, %M01.2.sroa.10.01174
  %.58.i460 = fmul fast double %.70.i, %M01.2.sroa.10.01174
  %.64.i461 = fmul fast double %.80.i, %M01.2.sroa.0.01175
  %.70.i462 = fsub fast double %.46.i458, %.52.i459
  %.46.i465 = fmul fast double %.112.i.i, %M11.2.sroa.0.01179
  %.52.i466 = fmul fast double %.121.i.i, %M11.2.sroa.10.01178
  %.58.i467 = fmul fast double %.112.i.i, %M11.2.sroa.10.01178
  %.64.i468 = fmul fast double %.121.i.i, %M11.2.sroa.0.01179
  %.70.i469 = fsub fast double %.46.i465, %.52.i466
  %.1048 = fadd fast double %.70.i462, %.70.i469
  %.80.i463 = fadd fast double %.58.i467, %.64.i468
  %.80.i470 = fadd fast double %.80.i463, %.64.i461
  %.1051 = fadd fast double %.80.i470, %.58.i460
  %.46.i472 = fmul fast double %.112.i.i, %Mb00.2.sroa.0.01181
  %.52.i473 = fmul fast double %.121.i.i, %Mb00.2.sroa.10.01180
  %.58.i474 = fmul fast double %.121.i.i, %Mb00.2.sroa.0.01181
  %.64.i475 = fmul fast double %.112.i.i, %Mb00.2.sroa.10.01180
  %.70.i476 = fsub fast double %.46.i472, %.52.i473
  %.46.i479 = fmul fast double %.70.i, %Mb01.2.sroa.0.01183
  %.52.i480 = fmul fast double %.80.i, %Mb01.2.sroa.10.01182
  %.58.i481 = fmul fast double %.80.i, %Mb01.2.sroa.0.01183
  %.64.i482 = fmul fast double %.70.i, %Mb01.2.sroa.10.01182
  %.70.i483 = fsub fast double %.46.i479, %.52.i480
  %.1129 = fadd fast double %.70.i483, %.70.i476
  %.80.i484 = fadd fast double %.58.i474, %.64.i475
  %.80.i477 = fadd fast double %.80.i484, %.64.i482
  %.1132 = fadd fast double %.80.i477, %.58.i481
  %.46.i486 = fmul fast double %"$phi576.1.2.sroa.0.1", %Mb00.2.sroa.0.01181
  %.52.i487 = fmul fast double %"$phi576.1.2.sroa.8.1", %Mb00.2.sroa.10.01180
  %.58.i488 = fmul fast double %"$phi576.1.2.sroa.8.1", %Mb00.2.sroa.0.01181
  %.64.i489 = fmul fast double %"$phi576.1.2.sroa.0.1", %Mb00.2.sroa.10.01180
  %.70.i490 = fsub fast double %.46.i486, %.52.i487
  %.46.i493 = fmul fast double %.112.i.i, %Mb01.2.sroa.0.01183
  %.52.i494 = fmul fast double %.121.i.i, %Mb01.2.sroa.10.01182
  %.58.i495 = fmul fast double %.121.i.i, %Mb01.2.sroa.0.01183
  %.64.i496 = fmul fast double %.112.i.i, %Mb01.2.sroa.10.01182
  %.70.i497 = fsub fast double %.46.i493, %.52.i494
  %.1210 = fadd fast double %.70.i490, %.70.i497
  %.80.i491 = fadd fast double %.58.i495, %.64.i496
  %.80.i498 = fadd fast double %.80.i491, %.58.i488
  %.1213 = fadd fast double %.80.i498, %.64.i489
  %.46.i500 = fmul fast double %.112.i.i, %Mb10.2.sroa.0.01185
  %.52.i501 = fmul fast double %.121.i.i, %Mb10.2.sroa.10.01184
  %.58.i502 = fmul fast double %.121.i.i, %Mb10.2.sroa.0.01185
  %.64.i503 = fmul fast double %.112.i.i, %Mb10.2.sroa.10.01184
  %.70.i504 = fsub fast double %.46.i500, %.52.i501
  %.46.i507 = fmul fast double %.70.i, %Mb11.2.sroa.0.01187
  %.52.i508 = fmul fast double %.80.i, %Mb11.2.sroa.10.01186
  %.58.i509 = fmul fast double %.80.i, %Mb11.2.sroa.0.01187
  %.64.i510 = fmul fast double %.70.i, %Mb11.2.sroa.10.01186
  %.70.i511 = fsub fast double %.46.i507, %.52.i508
  %.1291 = fadd fast double %.70.i511, %.70.i504
  %.80.i512 = fadd fast double %.58.i502, %.64.i503
  %.80.i505 = fadd fast double %.80.i512, %.64.i510
  %.1294 = fadd fast double %.80.i505, %.58.i509
  %.46.i514 = fmul fast double %"$phi576.1.2.sroa.0.1", %Mb10.2.sroa.0.01185
  %.52.i515 = fmul fast double %"$phi576.1.2.sroa.8.1", %Mb10.2.sroa.10.01184
  %.58.i516 = fmul fast double %"$phi576.1.2.sroa.8.1", %Mb10.2.sroa.0.01185
  %.64.i517 = fmul fast double %"$phi576.1.2.sroa.0.1", %Mb10.2.sroa.10.01184
  %.70.i518 = fsub fast double %.46.i514, %.52.i515
  %.46.i521 = fmul fast double %.112.i.i, %Mb11.2.sroa.0.01187
  %.52.i522 = fmul fast double %.121.i.i, %Mb11.2.sroa.10.01186
  %.58.i523 = fmul fast double %.121.i.i, %Mb11.2.sroa.0.01187
  %.64.i524 = fmul fast double %.112.i.i, %Mb11.2.sroa.10.01186
  %.70.i525 = fsub fast double %.46.i521, %.52.i522
  %.1374 = fadd fast double %.70.i518, %.70.i525
  %.80.i519 = fadd fast double %.58.i523, %.64.i524
  %.80.i526 = fadd fast double %.80.i519, %.58.i516
  %.1377 = fadd fast double %.80.i526, %.64.i517
  %scevgep583 = getelementptr i8, ptr %lsr.iv, i64 16
  %exitcond.not = icmp eq i64 %arg.thicknesses.5.0, %.253
  br i1 %exitcond.not, label %B1006, label %B254

B1006.endif:                                      ; preds = %B1006
  call void @llvm.memset.p0.i64(ptr noundef nonnull align 8 dereferenceable(16) %.1527, i8 0, i64 16, i1 false)
  %.1531 = call i32 @_ZN6certus7physics14certus_opt_tmm22compute_RT_from_matrixB3v11B76c8tJTIeFIjxB2IKSgI4CrvQCk0Z4yRYcWsCAgXrKFt1X1eogKfVaTWDAFsEMQEpRYBFNAA_3d_3dE10complex12810complex12810complex12810complex12810complex12810complex128(ptr nonnull %.1527, ptr nonnull %excinfo.27, double %Mb00.2.sroa.0.0.lcssa, double %Mb00.2.sroa.10.0.lcssa, double %Mb01.2.sroa.0.0.lcssa, double %Mb01.2.sroa.10.0.lcssa, double %Mb10.2.sroa.0.0.lcssa, double %Mb10.2.sroa.10.0.lcssa, double %Mb11.2.sroa.0.0.lcssa, double %Mb11.2.sroa.10.0.lcssa, double %arg.n_sub.0, double %arg.n_sub.1, double 1.000000e+00, double 0.000000e+00)
  %cond396 = icmp eq i32 %.1531, 0
  br i1 %cond396, label %B1006.endif.endif, label %B1006.endif.if.if, !prof !24

B1006.if.if:                                      ; preds = %B1006
  %.1486 = load ptr, ptr %excinfo.26, align 8
  store ptr %.1486, ptr %excinfo, align 8
  br label %common.ret

B1006.endif.endif:                                ; preds = %B1006.endif
  %.1541.fca.0.load = load double, ptr %.1527, align 8
  store double %.1495.fca.0.load, ptr %retptr, align 8
  %retptr.repack493 = getelementptr inbounds nuw i8, ptr %retptr, i64 8
  store double %.1495.fca.1.load, ptr %retptr.repack493, align 8
  %retptr.repack495 = getelementptr inbounds nuw i8, ptr %retptr, i64 16
  store double %.1541.fca.0.load, ptr %retptr.repack495, align 8
  br label %common.ret

B1006.endif.if.if:                                ; preds = %B1006.endif
  %.1532 = load ptr, ptr %excinfo.27, align 8
  store ptr %.1532, ptr %excinfo, align 8
  br label %common.ret
}

; Function Attrs: mustprogress nocallback nocreateundeforpoison nofree nosync nounwind speculatable willreturn memory(none)
declare double @llvm.sqrt.f64(double) #7

; Function Attrs: mustprogress nofree norecurse nosync nounwind willreturn memory(argmem: write)
define linkonce_odr noundef i32 @_ZN6certus7physics17certus_strat_math20_seeded_noise_sampleB3v26B76c8tJTIeFIjxB2IKSgI4CrvQCk0Z4yRYcWsCAgXrKFt1X1eogKfVaTWDAFsEMQEpRYBFNAA_3d_3dE23Literal_5bint_5d_280_2923Literal_5bint_5d_280_29y23Literal_5bint_5d_281_2927Literal_5bbool_5d_28True_29(ptr noalias writeonly captures(none) initializes((0, 8)) %retptr, ptr noalias readnone captures(none) %excinfo, i64 %arg.seed_base, i64 %arg.group_idx, i64 %arg.run_idx, i64 %arg.elem_idx, i8 %arg.gaussian) local_unnamed_addr #6 {
entry:
  %const = bitcast i64 2685821657736338717 to i64
  %0 = mul i64 %arg.run_idx, -4658895280553007687
  %.171 = add i64 %0, 6478314421090251831
  %.174 = lshr i64 %.171, 12
  %.175 = xor i64 %.174, %.171
  %.176 = shl i64 %.175, 25
  %.177 = xor i64 %.176, %.175
  %.178 = lshr i64 %.177, 27
  %.179 = xor i64 %.178, %.177
  %.180 = mul i64 %.179, %const
  %.181 = lshr i64 %.180, 11
  %.173.1 = add i64 %0, 3215249815922172618
  %.174.1 = lshr i64 %.173.1, 12
  %.175.1 = xor i64 %.174.1, %.173.1
  %.176.1 = shl i64 %.175.1, 25
  %.177.1 = xor i64 %.176.1, %.175.1
  %.178.1 = lshr i64 %.177.1, 27
  %.179.1 = xor i64 %.178.1, %.177.1
  %.180.1 = mul i64 %.179.1, %const
  %.181.1 = lshr i64 %.180.1, 11
  %1 = add nuw nsw i64 %.181.1, %.181
  %2 = uitofp nneg i64 %1 to double
  %.173.2 = add i64 %0, -47814789245906595
  %.174.2 = lshr i64 %.173.2, 12
  %.175.2 = xor i64 %.174.2, %.173.2
  %.176.2 = shl i64 %.175.2, 25
  %.177.2 = xor i64 %.176.2, %.175.2
  %.178.2 = lshr i64 %.177.2, 27
  %.179.2 = xor i64 %.178.2, %.177.2
  %.180.2 = mul i64 %.179.2, %const
  %.181.2 = lshr i64 %.180.2, 11
  %.173.3 = add i64 %0, -3310879394413985808
  %.174.3 = lshr i64 %.173.3, 12
  %.175.3 = xor i64 %.174.3, %.173.3
  %.176.3 = shl i64 %.175.3, 25
  %.177.3 = xor i64 %.176.3, %.175.3
  %.178.3 = lshr i64 %.177.3, 27
  %.179.3 = xor i64 %.178.3, %.177.3
  %.180.3 = mul i64 %.179.3, %const
  %.181.3 = lshr i64 %.180.3, 11
  %.173.4 = add i64 %0, -6573943999582065021
  %.174.4 = lshr i64 %.173.4, 12
  %.175.4 = xor i64 %.174.4, %.173.4
  %.176.4 = shl i64 %.175.4, 25
  %.177.4 = xor i64 %.176.4, %.175.4
  %.178.4 = lshr i64 %.177.4, 27
  %.179.4 = xor i64 %.178.4, %.177.4
  %.180.4 = mul i64 %.179.4, %const
  %.181.4 = lshr i64 %.180.4, 11
  %.173.5 = add i64 %0, 8609735468959407382
  %.174.5 = lshr i64 %.173.5, 12
  %.175.5 = xor i64 %.174.5, %.173.5
  %.176.5 = shl i64 %.175.5, 25
  %.177.5 = xor i64 %.176.5, %.175.5
  %.178.5 = lshr i64 %.177.5, 27
  %.179.5 = xor i64 %.178.5, %.177.5
  %.180.5 = mul i64 %.179.5, %const
  %.181.5 = lshr i64 %.180.5, 11
  %.173.6 = add i64 %0, 5346670863791328169
  %.174.6 = lshr i64 %.173.6, 12
  %.175.6 = xor i64 %.174.6, %.173.6
  %.176.6 = shl i64 %.175.6, 25
  %.177.6 = xor i64 %.176.6, %.175.6
  %.178.6 = lshr i64 %.177.6, 27
  %.179.6 = xor i64 %.178.6, %.177.6
  %.180.6 = mul i64 %.179.6, %const
  %.181.6 = lshr i64 %.180.6, 11
  %.173.7 = add i64 %0, 2083606258623248956
  %.174.7 = lshr i64 %.173.7, 12
  %.175.7 = xor i64 %.174.7, %.173.7
  %.176.7 = shl i64 %.175.7, 25
  %.177.7 = xor i64 %.176.7, %.175.7
  %.178.7 = lshr i64 %.177.7, 27
  %.179.7 = xor i64 %.178.7, %.177.7
  %.180.7 = mul i64 %.179.7, %const
  %.181.7 = lshr i64 %.180.7, 11
  %.173.8 = add i64 %0, -1179458346544830257
  %.174.8 = lshr i64 %.173.8, 12
  %.175.8 = xor i64 %.174.8, %.173.8
  %.176.8 = shl i64 %.175.8, 25
  %.177.8 = xor i64 %.176.8, %.175.8
  %.178.8 = lshr i64 %.177.8, 27
  %.179.8 = xor i64 %.178.8, %.177.8
  %.180.8 = mul i64 %.179.8, %const
  %.181.8 = lshr i64 %.180.8, 11
  %.173.9 = add i64 %0, -4442522951712909470
  %.174.9 = lshr i64 %.173.9, 12
  %.175.9 = xor i64 %.174.9, %.173.9
  %.176.9 = shl i64 %.175.9, 25
  %.177.9 = xor i64 %.176.9, %.175.9
  %.178.9 = lshr i64 %.177.9, 27
  %.179.9 = xor i64 %.178.9, %.177.9
  %.180.9 = mul i64 %.179.9, %const
  %.181.9 = lshr i64 %.180.9, 11
  %.173.10 = add i64 %0, -7705587556880988683
  %.174.10 = lshr i64 %.173.10, 12
  %.175.10 = xor i64 %.174.10, %.173.10
  %.176.10 = shl i64 %.175.10, 25
  %.177.10 = xor i64 %.176.10, %.175.10
  %.178.10 = lshr i64 %.177.10, 27
  %.179.10 = xor i64 %.178.10, %.177.10
  %.180.10 = mul i64 %.179.10, %const
  %.181.10 = lshr i64 %.180.10, 11
  %.173.11 = add i64 %0, 7478091911660483720
  %.174.11 = lshr i64 %.173.11, 12
  %.175.11 = xor i64 %.174.11, %.173.11
  %.176.11 = shl i64 %.175.11, 25
  %.177.11 = xor i64 %.176.11, %.175.11
  %.178.11 = lshr i64 %.177.11, 27
  %.179.11 = xor i64 %.178.11, %.177.11
  %.180.11 = mul i64 %.179.11, %const
  %.181.11 = lshr i64 %.180.11, 11
  %3 = add nuw nsw i64 %.181.3, %.181.2
  %4 = uitofp nneg i64 %3 to double
  %5 = add nuw nsw i64 %.181.5, %.181.4
  %6 = uitofp nneg i64 %5 to double
  %7 = add nuw nsw i64 %.181.7, %.181.6
  %8 = uitofp nneg i64 %7 to double
  %9 = add nuw nsw i64 %.181.9, %.181.8
  %10 = uitofp nneg i64 %9 to double
  %11 = add nuw nsw i64 %.181.11, %.181.10
  %12 = uitofp nneg i64 %11 to double
  %13 = fadd fast double %12, %10
  %14 = fadd fast double %13, %8
  %15 = fadd fast double %14, %6
  %16 = fadd fast double %15, %4
  %17 = fadd fast double %16, %2
  %18 = fmul fast double %17, 0x3C85555555555555
  %.202 = fadd fast double %18, -2.000000e+00
  %.214 = fcmp fast ogt double %.202, 1.000000e+00
  %..202 = select i1 %.214, double 1.000000e+00, double %.202
  %.inv = fcmp fast oge double %..202, -1.000000e+00
  %.202.sink47 = select nnan ninf i1 %.inv, double %..202, double -1.000000e+00
  store double %.202.sink47, ptr %retptr, align 8
  ret i32 0
}

; Function Attrs: mustprogress nocallback nocreateundeforpoison nofree nosync nounwind speculatable willreturn memory(none)
declare double @llvm.fabs.f64(double) #7

; Function Attrs: mustprogress nofree norecurse nosync nounwind willreturn memory(argmem: write)
define linkonce_odr noundef i32 @_ZN6certus7physics17certus_strat_math20_seeded_noise_sampleB3v27B76c8tJTIeFIjxB2IKSgI4CrvQCk0Z4yRYcWsCAgXrKFt1X1eogKfVaTWDAFsEMQEpRYBFNAA_3d_3dE23Literal_5bint_5d_280_2923Literal_5bint_5d_281_29y23Literal_5bint_5d_280_2927Literal_5bbool_5d_28True_29(ptr noalias writeonly captures(none) initializes((0, 8)) %retptr, ptr noalias readnone captures(none) %excinfo, i64 %arg.seed_base, i64 %arg.group_idx, i64 %arg.run_idx, i64 %arg.elem_idx, i8 %arg.gaussian) local_unnamed_addr #6 {
entry:
  %const = bitcast i64 2685821657736338717 to i64
  %0 = mul i64 %arg.run_idx, -4658895280553007687
  %.171 = add i64 %0, 7155877459814604385
  %.174 = lshr i64 %.171, 12
  %.175 = xor i64 %.174, %.171
  %.176 = shl i64 %.175, 25
  %.177 = xor i64 %.176, %.175
  %.178 = lshr i64 %.177, 27
  %.179 = xor i64 %.178, %.177
  %.180 = mul i64 %.179, %const
  %.181 = lshr i64 %.180, 11
  %.173.1 = add i64 %0, 3892812854646525172
  %.174.1 = lshr i64 %.173.1, 12
  %.175.1 = xor i64 %.174.1, %.173.1
  %.176.1 = shl i64 %.175.1, 25
  %.177.1 = xor i64 %.176.1, %.175.1
  %.178.1 = lshr i64 %.177.1, 27
  %.179.1 = xor i64 %.178.1, %.177.1
  %.180.1 = mul i64 %.179.1, %const
  %.181.1 = lshr i64 %.180.1, 11
  %1 = add nuw nsw i64 %.181.1, %.181
  %2 = uitofp nneg i64 %1 to double
  %.173.2 = add i64 %0, 629748249478445959
  %.174.2 = lshr i64 %.173.2, 12
  %.175.2 = xor i64 %.174.2, %.173.2
  %.176.2 = shl i64 %.175.2, 25
  %.177.2 = xor i64 %.176.2, %.175.2
  %.178.2 = lshr i64 %.177.2, 27
  %.179.2 = xor i64 %.178.2, %.177.2
  %.180.2 = mul i64 %.179.2, %const
  %.181.2 = lshr i64 %.180.2, 11
  %.173.3 = add i64 %0, -2633316355689633254
  %.174.3 = lshr i64 %.173.3, 12
  %.175.3 = xor i64 %.174.3, %.173.3
  %.176.3 = shl i64 %.175.3, 25
  %.177.3 = xor i64 %.176.3, %.175.3
  %.178.3 = lshr i64 %.177.3, 27
  %.179.3 = xor i64 %.178.3, %.177.3
  %.180.3 = mul i64 %.179.3, %const
  %.181.3 = lshr i64 %.180.3, 11
  %.173.4 = add i64 %0, -5896380960857712467
  %.174.4 = lshr i64 %.173.4, 12
  %.175.4 = xor i64 %.174.4, %.173.4
  %.176.4 = shl i64 %.175.4, 25
  %.177.4 = xor i64 %.176.4, %.175.4
  %.178.4 = lshr i64 %.177.4, 27
  %.179.4 = xor i64 %.178.4, %.177.4
  %.180.4 = mul i64 %.179.4, %const
  %.181.4 = lshr i64 %.180.4, 11
  %.173.5 = add i64 %0, -9159445566025791680
  %.174.5 = lshr i64 %.173.5, 12
  %.175.5 = xor i64 %.174.5, %.173.5
  %.176.5 = shl i64 %.175.5, 25
  %.177.5 = xor i64 %.176.5, %.175.5
  %.178.5 = lshr i64 %.177.5, 27
  %.179.5 = xor i64 %.178.5, %.177.5
  %.180.5 = mul i64 %.179.5, %const
  %.181.5 = lshr i64 %.180.5, 11
  %.173.6 = add i64 %0, 6024233902515680723
  %.174.6 = lshr i64 %.173.6, 12
  %.175.6 = xor i64 %.174.6, %.173.6
  %.176.6 = shl i64 %.175.6, 25
  %.177.6 = xor i64 %.176.6, %.175.6
  %.178.6 = lshr i64 %.177.6, 27
  %.179.6 = xor i64 %.178.6, %.177.6
  %.180.6 = mul i64 %.179.6, %const
  %.181.6 = lshr i64 %.180.6, 11
  %.173.7 = add i64 %0, 2761169297347601510
  %.174.7 = lshr i64 %.173.7, 12
  %.175.7 = xor i64 %.174.7, %.173.7
  %.176.7 = shl i64 %.175.7, 25
  %.177.7 = xor i64 %.176.7, %.175.7
  %.178.7 = lshr i64 %.177.7, 27
  %.179.7 = xor i64 %.178.7, %.177.7
  %.180.7 = mul i64 %.179.7, %const
  %.181.7 = lshr i64 %.180.7, 11
  %.173.8 = add i64 %0, -501895307820477703
  %.174.8 = lshr i64 %.173.8, 12
  %.175.8 = xor i64 %.174.8, %.173.8
  %.176.8 = shl i64 %.175.8, 25
  %.177.8 = xor i64 %.176.8, %.175.8
  %.178.8 = lshr i64 %.177.8, 27
  %.179.8 = xor i64 %.178.8, %.177.8
  %.180.8 = mul i64 %.179.8, %const
  %.181.8 = lshr i64 %.180.8, 11
  %.173.9 = add i64 %0, -3764959912988556916
  %.174.9 = lshr i64 %.173.9, 12
  %.175.9 = xor i64 %.174.9, %.173.9
  %.176.9 = shl i64 %.175.9, 25
  %.177.9 = xor i64 %.176.9, %.175.9
  %.178.9 = lshr i64 %.177.9, 27
  %.179.9 = xor i64 %.178.9, %.177.9
  %.180.9 = mul i64 %.179.9, %const
  %.181.9 = lshr i64 %.180.9, 11
  %.173.10 = add i64 %0, -7028024518156636129
  %.174.10 = lshr i64 %.173.10, 12
  %.175.10 = xor i64 %.174.10, %.173.10
  %.176.10 = shl i64 %.175.10, 25
  %.177.10 = xor i64 %.176.10, %.175.10
  %.178.10 = lshr i64 %.177.10, 27
  %.179.10 = xor i64 %.178.10, %.177.10
  %.180.10 = mul i64 %.179.10, %const
  %.181.10 = lshr i64 %.180.10, 11
  %.173.11 = add i64 %0, 8155654950384836274
  %.174.11 = lshr i64 %.173.11, 12
  %.175.11 = xor i64 %.174.11, %.173.11
  %.176.11 = shl i64 %.175.11, 25
  %.177.11 = xor i64 %.176.11, %.175.11
  %.178.11 = lshr i64 %.177.11, 27
  %.179.11 = xor i64 %.178.11, %.177.11
  %.180.11 = mul i64 %.179.11, %const
  %.181.11 = lshr i64 %.180.11, 11
  %3 = add nuw nsw i64 %.181.3, %.181.2
  %4 = uitofp nneg i64 %3 to double
  %5 = add nuw nsw i64 %.181.5, %.181.4
  %6 = uitofp nneg i64 %5 to double
  %7 = add nuw nsw i64 %.181.7, %.181.6
  %8 = uitofp nneg i64 %7 to double
  %9 = add nuw nsw i64 %.181.9, %.181.8
  %10 = uitofp nneg i64 %9 to double
  %11 = add nuw nsw i64 %.181.11, %.181.10
  %12 = uitofp nneg i64 %11 to double
  %13 = fadd fast double %12, %10
  %14 = fadd fast double %13, %8
  %15 = fadd fast double %14, %6
  %16 = fadd fast double %15, %4
  %17 = fadd fast double %16, %2
  %18 = fmul fast double %17, 0x3C85555555555555
  %.202 = fadd fast double %18, -2.000000e+00
  %.214 = fcmp fast ogt double %.202, 1.000000e+00
  %..202 = select i1 %.214, double 1.000000e+00, double %.202
  %.inv = fcmp fast oge double %..202, -1.000000e+00
  %.202.sink47 = select nnan ninf i1 %.inv, double %..202, double -1.000000e+00
  store double %.202.sink47, ptr %retptr, align 8
  ret i32 0
}

; Function Attrs: mustprogress nofree norecurse nosync nounwind willreturn memory(argmem: write)
define linkonce_odr noundef i32 @_ZN6certus7physics17certus_strat_math20_seeded_noise_sampleB3v28B76c8tJTIeFIjxB2IKSgI4CrvQCk0Z4yRYcWsCAgXrKFt1X1eogKfVaTWDAFsEMQEpRYBFNAA_3d_3dE23Literal_5bint_5d_280_2923Literal_5bint_5d_281_29y23Literal_5bint_5d_281_2927Literal_5bbool_5d_28True_29(ptr noalias writeonly captures(none) initializes((0, 8)) %retptr, ptr noalias readnone captures(none) %excinfo, i64 %arg.seed_base, i64 %arg.group_idx, i64 %arg.run_idx, i64 %arg.elem_idx, i8 %arg.gaussian) local_unnamed_addr #6 {
entry:
  %const = bitcast i64 2685821657736338717 to i64
  %0 = mul i64 %arg.run_idx, -4658895280553007687
  %.171 = add i64 %0, -567714833296101300
  %.174 = lshr i64 %.171, 12
  %.175 = xor i64 %.174, %.171
  %.176 = shl i64 %.175, 25
  %.177 = xor i64 %.176, %.175
  %.178 = lshr i64 %.177, 27
  %.179 = xor i64 %.178, %.177
  %.180 = mul i64 %.179, %const
  %.181 = lshr i64 %.180, 11
  %.173.1 = add i64 %0, -3830779438464180513
  %.174.1 = lshr i64 %.173.1, 12
  %.175.1 = xor i64 %.174.1, %.173.1
  %.176.1 = shl i64 %.175.1, 25
  %.177.1 = xor i64 %.176.1, %.175.1
  %.178.1 = lshr i64 %.177.1, 27
  %.179.1 = xor i64 %.178.1, %.177.1
  %.180.1 = mul i64 %.179.1, %const
  %.181.1 = lshr i64 %.180.1, 11
  %1 = add nuw nsw i64 %.181.1, %.181
  %2 = uitofp nneg i64 %1 to double
  %.173.2 = add i64 %0, -7093844043632259726
  %.174.2 = lshr i64 %.173.2, 12
  %.175.2 = xor i64 %.174.2, %.173.2
  %.176.2 = shl i64 %.175.2, 25
  %.177.2 = xor i64 %.176.2, %.175.2
  %.178.2 = lshr i64 %.177.2, 27
  %.179.2 = xor i64 %.178.2, %.177.2
  %.180.2 = mul i64 %.179.2, %const
  %.181.2 = lshr i64 %.180.2, 11
  %.173.3 = add i64 %0, 8089835424909212677
  %.174.3 = lshr i64 %.173.3, 12
  %.175.3 = xor i64 %.174.3, %.173.3
  %.176.3 = shl i64 %.175.3, 25
  %.177.3 = xor i64 %.176.3, %.175.3
  %.178.3 = lshr i64 %.177.3, 27
  %.179.3 = xor i64 %.178.3, %.177.3
  %.180.3 = mul i64 %.179.3, %const
  %.181.3 = lshr i64 %.180.3, 11
  %.173.4 = add i64 %0, 4826770819741133464
  %.174.4 = lshr i64 %.173.4, 12
  %.175.4 = xor i64 %.174.4, %.173.4
  %.176.4 = shl i64 %.175.4, 25
  %.177.4 = xor i64 %.176.4, %.175.4
  %.178.4 = lshr i64 %.177.4, 27
  %.179.4 = xor i64 %.178.4, %.177.4
  %.180.4 = mul i64 %.179.4, %const
  %.181.4 = lshr i64 %.180.4, 11
  %.173.5 = add i64 %0, 1563706214573054251
  %.174.5 = lshr i64 %.173.5, 12
  %.175.5 = xor i64 %.174.5, %.173.5
  %.176.5 = shl i64 %.175.5, 25
  %.177.5 = xor i64 %.176.5, %.175.5
  %.178.5 = lshr i64 %.177.5, 27
  %.179.5 = xor i64 %.178.5, %.177.5
  %.180.5 = mul i64 %.179.5, %const
  %.181.5 = lshr i64 %.180.5, 11
  %.173.6 = add i64 %0, -1699358390595024962
  %.174.6 = lshr i64 %.173.6, 12
  %.175.6 = xor i64 %.174.6, %.173.6
  %.176.6 = shl i64 %.175.6, 25
  %.177.6 = xor i64 %.176.6, %.175.6
  %.178.6 = lshr i64 %.177.6, 27
  %.179.6 = xor i64 %.178.6, %.177.6
  %.180.6 = mul i64 %.179.6, %const
  %.181.6 = lshr i64 %.180.6, 11
  %.173.7 = add i64 %0, -4962422995763104175
  %.174.7 = lshr i64 %.173.7, 12
  %.175.7 = xor i64 %.174.7, %.173.7
  %.176.7 = shl i64 %.175.7, 25
  %.177.7 = xor i64 %.176.7, %.175.7
  %.178.7 = lshr i64 %.177.7, 27
  %.179.7 = xor i64 %.178.7, %.177.7
  %.180.7 = mul i64 %.179.7, %const
  %.181.7 = lshr i64 %.180.7, 11
  %.173.8 = add i64 %0, -8225487600931183388
  %.174.8 = lshr i64 %.173.8, 12
  %.175.8 = xor i64 %.174.8, %.173.8
  %.176.8 = shl i64 %.175.8, 25
  %.177.8 = xor i64 %.176.8, %.175.8
  %.178.8 = lshr i64 %.177.8, 27
  %.179.8 = xor i64 %.178.8, %.177.8
  %.180.8 = mul i64 %.179.8, %const
  %.181.8 = lshr i64 %.180.8, 11
  %.173.9 = add i64 %0, 6958191867610289015
  %.174.9 = lshr i64 %.173.9, 12
  %.175.9 = xor i64 %.174.9, %.173.9
  %.176.9 = shl i64 %.175.9, 25
  %.177.9 = xor i64 %.176.9, %.175.9
  %.178.9 = lshr i64 %.177.9, 27
  %.179.9 = xor i64 %.178.9, %.177.9
  %.180.9 = mul i64 %.179.9, %const
  %.181.9 = lshr i64 %.180.9, 11
  %.173.10 = add i64 %0, 3695127262442209802
  %.174.10 = lshr i64 %.173.10, 12
  %.175.10 = xor i64 %.174.10, %.173.10
  %.176.10 = shl i64 %.175.10, 25
  %.177.10 = xor i64 %.176.10, %.175.10
  %.178.10 = lshr i64 %.177.10, 27
  %.179.10 = xor i64 %.178.10, %.177.10
  %.180.10 = mul i64 %.179.10, %const
  %.181.10 = lshr i64 %.180.10, 11
  %.173.11 = add i64 %0, 432062657274130589
  %.174.11 = lshr i64 %.173.11, 12
  %.175.11 = xor i64 %.174.11, %.173.11
  %.176.11 = shl i64 %.175.11, 25
  %.177.11 = xor i64 %.176.11, %.175.11
  %.178.11 = lshr i64 %.177.11, 27
  %.179.11 = xor i64 %.178.11, %.177.11
  %.180.11 = mul i64 %.179.11, %const
  %.181.11 = lshr i64 %.180.11, 11
  %3 = add nuw nsw i64 %.181.3, %.181.2
  %4 = uitofp nneg i64 %3 to double
  %5 = add nuw nsw i64 %.181.5, %.181.4
  %6 = uitofp nneg i64 %5 to double
  %7 = add nuw nsw i64 %.181.7, %.181.6
  %8 = uitofp nneg i64 %7 to double
  %9 = add nuw nsw i64 %.181.9, %.181.8
  %10 = uitofp nneg i64 %9 to double
  %11 = add nuw nsw i64 %.181.11, %.181.10
  %12 = uitofp nneg i64 %11 to double
  %13 = fadd fast double %12, %10
  %14 = fadd fast double %13, %8
  %15 = fadd fast double %14, %6
  %16 = fadd fast double %15, %4
  %17 = fadd fast double %16, %2
  %18 = fmul fast double %17, 0x3C85555555555555
  %.202 = fadd fast double %18, -2.000000e+00
  %.214 = fcmp fast ogt double %.202, 1.000000e+00
  %..202 = select i1 %.214, double 1.000000e+00, double %.202
  %.inv = fcmp fast oge double %..202, -1.000000e+00
  %.202.sink47 = select nnan ninf i1 %.inv, double %..202, double -1.000000e+00
  store double %.202.sink47, ptr %retptr, align 8
  ret i32 0
}

; Function Attrs: mustprogress nocallback nocreateundeforpoison nofree nosync nounwind speculatable willreturn memory(none)
declare double @llvm.cos.f64(double) #7

; Function Attrs: mustprogress nocallback nofree nosync nounwind willreturn memory(none)
declare double @cosh(double) local_unnamed_addr #8

; Function Attrs: mustprogress nocallback nocreateundeforpoison nofree nosync nounwind speculatable willreturn memory(none)
declare double @llvm.sin.f64(double) #7

; Function Attrs: mustprogress nocallback nofree nosync nounwind willreturn memory(none)
declare double @sinh(double) local_unnamed_addr #8

declare double @_hypot(double, double) local_unnamed_addr

define linkonce_odr range(i32 0, 2) i32 @_ZN6certus7physics14certus_opt_tmm22compute_RT_from_matrixB3v11B76c8tJTIeFIjxB2IKSgI4CrvQCk0Z4yRYcWsCAgXrKFt1X1eogKfVaTWDAFsEMQEpRYBFNAA_3d_3dE10complex12810complex12810complex12810complex12810complex12810complex128(ptr noalias writeonly captures(none) %retptr, ptr noalias writeonly captures(none) %excinfo, double %arg.M00.0, double %arg.M00.1, double %arg.M01.0, double %arg.M01.1, double %arg.M10.0, double %arg.M10.1, double %arg.M11.0, double %arg.M11.1, double %arg.n_inc.0, double %arg.n_inc.1, double %arg.n_exit.0, double %arg.n_exit.1) local_unnamed_addr {
B0.endif.endif.endif.endif:
  %.46.i = fmul fast double %arg.n_exit.0, %arg.M01.0
  %.52.i = fmul fast double %arg.n_exit.1, %arg.M01.1
  %.58.i = fmul fast double %arg.n_exit.1, %arg.M01.0
  %.64.i = fmul fast double %arg.n_exit.0, %arg.M01.1
  %.70.i = fsub fast double %.46.i, %.52.i
  %.68 = fadd fast double %.70.i, %arg.M00.0
  %.80.i = fadd fast double %.64.i, %arg.M00.1
  %.71 = fadd fast double %.80.i, %.58.i
  %.46.i11 = fmul fast double %arg.n_exit.0, %arg.M11.0
  %.52.i12 = fmul fast double %arg.n_exit.1, %arg.M11.1
  %.58.i13 = fmul fast double %arg.n_exit.1, %arg.M11.0
  %.64.i14 = fmul fast double %arg.n_exit.0, %arg.M11.1
  %.70.i15 = fsub fast double %.46.i11, %.52.i12
  %.124 = fadd fast double %.70.i15, %arg.M10.0
  %.80.i16 = fadd fast double %.64.i14, %arg.M10.1
  %.127 = fadd fast double %.80.i16, %.58.i13
  %.46.i18 = fmul fast double %.68, %arg.n_inc.0
  %.52.i19 = fmul fast double %.71, %arg.n_inc.1
  %.58.i20 = fmul fast double %.71, %arg.n_inc.0
  %.64.i21 = fmul fast double %.68, %arg.n_inc.1
  %.70.i22 = fsub fast double %.46.i18, %.52.i19
  %.80.i23 = fadd fast double %.64.i21, %.58.i20
  %.182 = fadd fast double %.70.i22, %.124
  %.185 = fadd fast double %.80.i23, %.127
  %.6.i.i25 = tail call fast double @_hypot(double %.182, double %.185), !noalias !66
  %.217 = fcmp fast olt double %.6.i.i25, 0x3D06849B86A12B9B
  br i1 %.217, label %B124, label %B130.endif

common.ret:                                       ; preds = %B404.endif, %B130.endif.if.if, %B124
  %common.ret.op = phi i32 [ 0, %B124 ], [ 1, %B130.endif.if.if ], [ 0, %B404.endif ]
  ret i32 %common.ret.op

B124:                                             ; preds = %B0.endif.endif.endif.endif
  tail call void @llvm.memset.p0.i64(ptr noundef nonnull align 8 dereferenceable(16) %retptr, i8 0, i64 16, i1 false)
  br label %common.ret

B130.endif:                                       ; preds = %B0.endif.endif.endif.endif
  %.289 = fsub fast double %.70.i22, %.124
  %.292 = fsub fast double %.80.i23, %.127
  %.45.i = tail call fast double @llvm.fabs.f64(double %.182)
  %.50.i = tail call fast double @llvm.fabs.f64(double %.185)
  %.56.i = fcmp fast ult double %.45.i, %.50.i
  br i1 %.56.i, label %B344.i, label %B154.i

B154.i:                                           ; preds = %B130.endif
  %.59.i = fcmp fast oeq double %.182, 0.000000e+00
  br i1 %.59.i, label %B130.endif.if.if, label %B192.endif.i

B344.i:                                           ; preds = %B130.endif
  %.132.i = fcmp fast ult double %.50.i, %.45.i
  br i1 %.132.i, label %B130.endif.endif.endif, label %B354.i

B354.i:                                           ; preds = %B344.i
  %.136.i = fcmp fast oeq double %.185, 0.000000e+00
  br i1 %.136.i, label %B130.endif.if.if, label %B354.endif.i, !prof !0

B192.endif.i:                                     ; preds = %B154.i
  %.89.i = fdiv fast double %.185, %.182
  %.91.i = fmul fast double %.89.i, %.185
  %.93.i = fadd fast double %.91.i, %.182
  %.98.i = fcmp fast oeq double %.93.i, 0.000000e+00
  br i1 %.98.i, label %B130.endif.if.if, label %B192.endif.endif.endif.i, !prof !0

B192.endif.endif.endif.i:                         ; preds = %B192.endif.i
  %.95.i = fmul fast double %.89.i, %.292
  %.97.i = fadd fast double %.95.i, %.289
  %.105.i = fdiv fast double %.97.i, %.93.i
  %.107.i = fmul fast double %.89.i, %.289
  %.109.i = fsub fast double %.292, %.107.i
  %.117.i = fdiv fast double %.109.i, %.93.i
  br label %B130.endif.endif.endif

B354.endif.i:                                     ; preds = %B354.i
  %.143.i = fdiv fast double %.182, %.185
  %.145.i = fmul fast double %.143.i, %.182
  %.147.i = fadd fast double %.145.i, %.185
  %.152.i = fcmp fast oeq double %.147.i, 0.000000e+00
  br i1 %.152.i, label %B130.endif.if.if, label %B354.endif.endif.endif.i, !prof !0

B354.endif.endif.endif.i:                         ; preds = %B354.endif.i
  %.149.i = fmul fast double %.143.i, %.289
  %.151.i = fadd fast double %.149.i, %.292
  %.159.i = fdiv fast double %.151.i, %.147.i
  %.161.i = fmul fast double %.143.i, %.292
  %.163.i = fsub fast double %.161.i, %.289
  %.171.i = fdiv fast double %.163.i, %.147.i
  br label %B130.endif.endif.endif

B130.endif.if.if:                                 ; preds = %B354.endif.i, %B192.endif.i, %B354.i, %B154.i
  %excinfo.6.0.ph = phi ptr [ @.const.picklebuf.b28008a0f88bad5ff0f0243e84dab90cab19b366.15, %B354.endif.i ], [ @.const.picklebuf.b28008a0f88bad5ff0f0243e84dab90cab19b366.15, %B354.i ], [ @.const.picklebuf.b28008a0f88bad5ff0f0243e84dab90cab19b366.15, %B192.endif.i ], [ @.const.picklebuf.b6e474b50ffce3a1cb8e957957228030e14ea2dc.16, %B154.i ]
  store ptr %excinfo.6.0.ph, ptr %excinfo, align 8
  br label %common.ret

B130.endif.endif.endif:                           ; preds = %B354.endif.endif.endif.i, %B192.endif.endif.endif.i, %B344.i
  %.299.sroa.0.0 = phi double [ 0x7FF8000000000000, %B344.i ], [ %.105.i, %B192.endif.endif.endif.i ], [ %.159.i, %B354.endif.endif.endif.i ]
  %.299.sroa.4.0 = phi double [ 0x7FF8000000000000, %B344.i ], [ %.117.i, %B192.endif.endif.endif.i ], [ %.171.i, %B354.endif.endif.endif.i ]
  %.6.i.i26 = tail call fast double @_hypot(double %.299.sroa.0.0, double %.299.sroa.4.0), !noalias !71
  %.137.i = fmul fast double %.6.i.i26, %.6.i.i26
  %.387 = fcmp fast olt double %arg.n_inc.0, 1.000000e-09
  br i1 %.387, label %B404.endif, label %B254.endif

B254.endif:                                       ; preds = %B130.endif.endif.endif
  %.6.i.i = tail call fast double @_hypot(double %arg.n_inc.0, double %arg.n_inc.1), !noalias !76
  %.6.i.i44 = tail call fast double @_hypot(double %.182, double %.185), !noalias !81
  %0 = fmul fast double %arg.n_exit.0, 4.000000e+00
  %1 = fmul fast double %.6.i.i, %.6.i.i
  %2 = fmul fast double %1, %0
  %3 = fmul fast double %.6.i.i44, %.6.i.i44
  %4 = fmul fast double %3, %arg.n_inc.0
  %.524 = fdiv fast double %2, %4
  br label %B404.endif

B404.endif:                                       ; preds = %B254.endif, %B130.endif.endif.endif
  %T.3.0 = phi double [ %.524, %B254.endif ], [ 0.000000e+00, %B130.endif.endif.endif ]
  %.12.i = fcmp fast ogt double %T.3.0, 0.000000e+00
  %.13.i = select i1 %.12.i, double %T.3.0, double 0.000000e+00
  store double %.137.i, ptr %retptr, align 8
  %retptr.repack119 = getelementptr inbounds nuw i8, ptr %retptr, i64 8
  store double %.13.i, ptr %retptr.repack119, align 8
  br label %common.ret
}

; Function Attrs: nocallback nofree nosync nounwind willreturn memory(argmem: readwrite)
declare void @llvm.lifetime.start.p0(ptr captures(none)) #9

; Function Attrs: nocallback nofree nosync nounwind willreturn memory(argmem: readwrite)
declare void @llvm.lifetime.end.p0(ptr captures(none)) #9

attributes #0 = { mustprogress nocallback nofree nounwind willreturn memory(argmem: write) }
attributes #1 = { nofree nounwind }
attributes #2 = { mustprogress nocallback nofree nosync nounwind willreturn memory(inaccessiblemem: readwrite) }
attributes #3 = { noinline }
attributes #4 = { nounwind }
attributes #5 = { mustprogress nofree noinline norecurse nounwind willreturn memory(argmem: readwrite) }
attributes #6 = { mustprogress nofree norecurse nosync nounwind willreturn memory(argmem: write) }
attributes #7 = { mustprogress nocallback nocreateundeforpoison nofree nosync nounwind speculatable willreturn memory(none) }
attributes #8 = { mustprogress nocallback nofree nosync nounwind willreturn memory(none) }
attributes #9 = { nocallback nofree nosync nounwind willreturn memory(argmem: readwrite) }

!0 = !{!"branch_weights", i32 1, i32 99}
!1 = !{!2, !4, !5, !7, !8, !10}
!2 = distinct !{!2, !3, !"_ZN5numba2np8arrayobj18_ol_array_allocate12_3clocals_3e4implB2v4B42c8tJTIeFIjxB2IKSgI4CrvQClcaMQ5hEEUSJJgA_3dEN29typeref_5b_3cclass_20_27numba4core5types8npytypes14Array_27_3e_5dExj: %retptr"}
!3 = distinct !{!3, !"_ZN5numba2np8arrayobj18_ol_array_allocate12_3clocals_3e4implB2v4B42c8tJTIeFIjxB2IKSgI4CrvQClcaMQ5hEEUSJJgA_3dEN29typeref_5b_3cclass_20_27numba4core5types8npytypes14Array_27_3e_5dExj"}
!4 = distinct !{!4, !3, !"_ZN5numba2np8arrayobj18_ol_array_allocate12_3clocals_3e4implB2v4B42c8tJTIeFIjxB2IKSgI4CrvQClcaMQ5hEEUSJJgA_3dEN29typeref_5b_3cclass_20_27numba4core5types8npytypes14Array_27_3e_5dExj: %excinfo"}
!5 = distinct !{!5, !6, !"_ZN5numba2np8arrayobj15_call_allocatorB2v3B42c8tJTC_2fWQA93W1AaAIYBPIqRBFCjDSZRVAJmaQIAEN29typeref_5b_3cclass_20_27numba4core5types8npytypes14Array_27_3e_5dExj: %retptr"}
!6 = distinct !{!6, !"_ZN5numba2np8arrayobj15_call_allocatorB2v3B42c8tJTC_2fWQA93W1AaAIYBPIqRBFCjDSZRVAJmaQIAEN29typeref_5b_3cclass_20_27numba4core5types8npytypes14Array_27_3e_5dExj"}
!7 = distinct !{!7, !6, !"_ZN5numba2np8arrayobj15_call_allocatorB2v3B42c8tJTC_2fWQA93W1AaAIYBPIqRBFCjDSZRVAJmaQIAEN29typeref_5b_3cclass_20_27numba4core5types8npytypes14Array_27_3e_5dExj: %excinfo"}
!8 = distinct !{!8, !9, !"_ZN5numba2np8arrayobj11ol_np_empty12_3clocals_3e4implB3v22B74c8tJTIeFIjxB2IKSgI4CrvQCk0Z4yRYcWsCAgXrKFt1X1eogKfVaTWDAYkQ91Dxg0IFZmgA_3dEx18class_28float64_29: %retptr"}
!9 = distinct !{!9, !"_ZN5numba2np8arrayobj11ol_np_empty12_3clocals_3e4implB3v22B74c8tJTIeFIjxB2IKSgI4CrvQCk0Z4yRYcWsCAgXrKFt1X1eogKfVaTWDAYkQ91Dxg0IFZmgA_3dEx18class_28float64_29"}
!10 = distinct !{!10, !9, !"_ZN5numba2np8arrayobj11ol_np_empty12_3clocals_3e4implB3v22B74c8tJTIeFIjxB2IKSgI4CrvQCk0Z4yRYcWsCAgXrKFt1X1eogKfVaTWDAYkQ91Dxg0IFZmgA_3dEx18class_28float64_29: %excinfo"}
!11 = !{!8, !10}
!12 = !{!13, !15, !16, !18, !19, !21}
!13 = distinct !{!13, !14, !"_ZN5numba2np8arrayobj18_ol_array_allocate12_3clocals_3e4implB2v4B42c8tJTIeFIjxB2IKSgI4CrvQClcaMQ5hEEUSJJgA_3dEN29typeref_5b_3cclass_20_27numba4core5types8npytypes14Array_27_3e_5dExj: %retptr"}
!14 = distinct !{!14, !"_ZN5numba2np8arrayobj18_ol_array_allocate12_3clocals_3e4implB2v4B42c8tJTIeFIjxB2IKSgI4CrvQClcaMQ5hEEUSJJgA_3dEN29typeref_5b_3cclass_20_27numba4core5types8npytypes14Array_27_3e_5dExj"}
!15 = distinct !{!15, !14, !"_ZN5numba2np8arrayobj18_ol_array_allocate12_3clocals_3e4implB2v4B42c8tJTIeFIjxB2IKSgI4CrvQClcaMQ5hEEUSJJgA_3dEN29typeref_5b_3cclass_20_27numba4core5types8npytypes14Array_27_3e_5dExj: %excinfo"}
!16 = distinct !{!16, !17, !"_ZN5numba2np8arrayobj15_call_allocatorB2v3B42c8tJTC_2fWQA93W1AaAIYBPIqRBFCjDSZRVAJmaQIAEN29typeref_5b_3cclass_20_27numba4core5types8npytypes14Array_27_3e_5dExj: %retptr"}
!17 = distinct !{!17, !"_ZN5numba2np8arrayobj15_call_allocatorB2v3B42c8tJTC_2fWQA93W1AaAIYBPIqRBFCjDSZRVAJmaQIAEN29typeref_5b_3cclass_20_27numba4core5types8npytypes14Array_27_3e_5dExj"}
!18 = distinct !{!18, !17, !"_ZN5numba2np8arrayobj15_call_allocatorB2v3B42c8tJTC_2fWQA93W1AaAIYBPIqRBFCjDSZRVAJmaQIAEN29typeref_5b_3cclass_20_27numba4core5types8npytypes14Array_27_3e_5dExj: %excinfo"}
!19 = distinct !{!19, !20, !"_ZN5numba2np8arrayobj11ol_np_empty12_3clocals_3e4implB3v22B74c8tJTIeFIjxB2IKSgI4CrvQCk0Z4yRYcWsCAgXrKFt1X1eogKfVaTWDAYkQ91Dxg0IFZmgA_3dEx18class_28float64_29: %retptr"}
!20 = distinct !{!20, !"_ZN5numba2np8arrayobj11ol_np_empty12_3clocals_3e4implB3v22B74c8tJTIeFIjxB2IKSgI4CrvQCk0Z4yRYcWsCAgXrKFt1X1eogKfVaTWDAYkQ91Dxg0IFZmgA_3dEx18class_28float64_29"}
!21 = distinct !{!21, !20, !"_ZN5numba2np8arrayobj11ol_np_empty12_3clocals_3e4implB3v22B74c8tJTIeFIjxB2IKSgI4CrvQCk0Z4yRYcWsCAgXrKFt1X1eogKfVaTWDAYkQ91Dxg0IFZmgA_3dEx18class_28float64_29: %excinfo"}
!22 = !{!19, !21}
!23 = !{i1 true}
!24 = !{!"branch_weights", i32 49, i32 1}
!25 = !{!26}
!26 = distinct !{!26, !27, !"_ZN13_3cdynamic_3e35__numba_parfor_gufunc_0x24b561942f0B3v23B138c8tJTC_2fWQAliW1xhDEoY6EEMEUOEMISPGsAQMVj4QniQ4IXKQEMXwoMGLoQDDVsQR1NHAS2hQ9XgStYwaUTI24JtBVoBDXtb9MCvVgdJqdcC7YLGAMy5RSVwr8KzAcRZAA_3d_3dE5ArrayIyLi1E1C7mutable7alignedE5ArrayIdLi1E1C7mutable7alignedE5ArrayIdLi1E1C7mutable7alignedE: %arg.sched.4"}
!27 = distinct !{!27, !"_ZN13_3cdynamic_3e35__numba_parfor_gufunc_0x24b561942f0B3v23B138c8tJTC_2fWQAliW1xhDEoY6EEMEUOEMISPGsAQMVj4QniQ4IXKQEMXwoMGLoQDDVsQR1NHAS2hQ9XgStYwaUTI24JtBVoBDXtb9MCvVgdJqdcC7YLGAMy5RSVwr8KzAcRZAA_3d_3dE5ArrayIyLi1E1C7mutable7alignedE5ArrayIdLi1E1C7mutable7alignedE5ArrayIdLi1E1C7mutable7alignedE"}
!28 = !{!29}
!29 = distinct !{!29, !27, !"_ZN13_3cdynamic_3e35__numba_parfor_gufunc_0x24b561942f0B3v23B138c8tJTC_2fWQAliW1xhDEoY6EEMEUOEMISPGsAQMVj4QniQ4IXKQEMXwoMGLoQDDVsQR1NHAS2hQ9XgStYwaUTI24JtBVoBDXtb9MCvVgdJqdcC7YLGAMy5RSVwr8KzAcRZAA_3d_3dE5ArrayIyLi1E1C7mutable7alignedE5ArrayIdLi1E1C7mutable7alignedE5ArrayIdLi1E1C7mutable7alignedE: %arg.wls.4"}
!30 = !{!31}
!31 = distinct !{!31, !27, !"_ZN13_3cdynamic_3e35__numba_parfor_gufunc_0x24b561942f0B3v23B138c8tJTC_2fWQAliW1xhDEoY6EEMEUOEMISPGsAQMVj4QniQ4IXKQEMXwoMGLoQDDVsQR1NHAS2hQ9XgStYwaUTI24JtBVoBDXtb9MCvVgdJqdcC7YLGAMy5RSVwr8KzAcRZAA_3d_3dE5ArrayIyLi1E1C7mutable7alignedE5ArrayIdLi1E1C7mutable7alignedE5ArrayIdLi1E1C7mutable7alignedE: %arg.k0__arr.4"}
!32 = !{!33, !29, !31}
!33 = distinct !{!33, !27, !"_ZN13_3cdynamic_3e35__numba_parfor_gufunc_0x24b561942f0B3v23B138c8tJTC_2fWQAliW1xhDEoY6EEMEUOEMISPGsAQMVj4QniQ4IXKQEMXwoMGLoQDDVsQR1NHAS2hQ9XgStYwaUTI24JtBVoBDXtb9MCvVgdJqdcC7YLGAMy5RSVwr8KzAcRZAA_3d_3dE5ArrayIyLi1E1C7mutable7alignedE5ArrayIdLi1E1C7mutable7alignedE5ArrayIdLi1E1C7mutable7alignedE: %retptr"}
!34 = !{!33, !26, !31}
!35 = !{!33, !26, !29}
!36 = distinct !{!36, !37, !38}
!37 = !{!"llvm.loop.isvectorized", i32 1}
!38 = !{!"llvm.loop.unroll.runtime.disable"}
!39 = distinct !{!39, !38, !37}
!40 = !{!41, !43, !44, !46, !47, !49}
!41 = distinct !{!41, !42, !"_ZN5numba2np8arrayobj18_ol_array_allocate12_3clocals_3e4implB2v4B42c8tJTIeFIjxB2IKSgI4CrvQClcaMQ5hEEUSJJgA_3dEN29typeref_5b_3cclass_20_27numba4core5types8npytypes14Array_27_3e_5dExj: %retptr"}
!42 = distinct !{!42, !"_ZN5numba2np8arrayobj18_ol_array_allocate12_3clocals_3e4implB2v4B42c8tJTIeFIjxB2IKSgI4CrvQClcaMQ5hEEUSJJgA_3dEN29typeref_5b_3cclass_20_27numba4core5types8npytypes14Array_27_3e_5dExj"}
!43 = distinct !{!43, !42, !"_ZN5numba2np8arrayobj18_ol_array_allocate12_3clocals_3e4implB2v4B42c8tJTIeFIjxB2IKSgI4CrvQClcaMQ5hEEUSJJgA_3dEN29typeref_5b_3cclass_20_27numba4core5types8npytypes14Array_27_3e_5dExj: %excinfo"}
!44 = distinct !{!44, !45, !"_ZN5numba2np8arrayobj15_call_allocatorB2v3B42c8tJTC_2fWQA93W1AaAIYBPIqRBFCjDSZRVAJmaQIAEN29typeref_5b_3cclass_20_27numba4core5types8npytypes14Array_27_3e_5dExj: %retptr"}
!45 = distinct !{!45, !"_ZN5numba2np8arrayobj15_call_allocatorB2v3B42c8tJTC_2fWQA93W1AaAIYBPIqRBFCjDSZRVAJmaQIAEN29typeref_5b_3cclass_20_27numba4core5types8npytypes14Array_27_3e_5dExj"}
!46 = distinct !{!46, !45, !"_ZN5numba2np8arrayobj15_call_allocatorB2v3B42c8tJTC_2fWQA93W1AaAIYBPIqRBFCjDSZRVAJmaQIAEN29typeref_5b_3cclass_20_27numba4core5types8npytypes14Array_27_3e_5dExj: %excinfo"}
!47 = distinct !{!47, !48, !"_ZN5numba2np8arrayobj11ol_np_empty12_3clocals_3e4implB2v9B74c8tJTIeFIjxB2IKSgI4CrvQCk0Z4yRYcWsCAgXrKFt1X1eogKfVaTWDAYkQ91Dxg0IFZmgA_3dEx21class_28complex128_29: %retptr"}
!48 = distinct !{!48, !"_ZN5numba2np8arrayobj11ol_np_empty12_3clocals_3e4implB2v9B74c8tJTIeFIjxB2IKSgI4CrvQCk0Z4yRYcWsCAgXrKFt1X1eogKfVaTWDAYkQ91Dxg0IFZmgA_3dEx21class_28complex128_29"}
!49 = distinct !{!49, !48, !"_ZN5numba2np8arrayobj11ol_np_empty12_3clocals_3e4implB2v9B74c8tJTIeFIjxB2IKSgI4CrvQCk0Z4yRYcWsCAgXrKFt1X1eogKfVaTWDAYkQ91Dxg0IFZmgA_3dEx21class_28complex128_29: %excinfo"}
!50 = !{!"branch_weights", i32 1, i32 49, i32 49}
!51 = !{!52}
!52 = distinct !{!52, !53}
!53 = distinct !{!53, !"LVerDomain"}
!54 = !{!55}
!55 = distinct !{!55, !53}
!56 = distinct !{!56, !37, !38}
!57 = distinct !{!57, !58}
!58 = !{!"llvm.loop.unroll.disable"}
!59 = !{!47, !49}
!60 = distinct !{!60, !37}
!61 = !{!62, !64}
!62 = distinct !{!62, !63, !"_ZN5numba7cpython8mathimpl16hypot_float_impl12_3clocals_3e10hypot_implB3v15B42c8tJTC_2fWQA93W1AaAIYBPIqRBFCjDSZRVAJmaQIAEdd: %retptr"}
!63 = distinct !{!63, !"_ZN5numba7cpython8mathimpl16hypot_float_impl12_3clocals_3e10hypot_implB3v15B42c8tJTC_2fWQA93W1AaAIYBPIqRBFCjDSZRVAJmaQIAEdd"}
!64 = distinct !{!64, !65, !"_ZN5numba7cpython7numbers16complex_abs_impl12_3clocals_3e11complex_absB3v14B42c8tJTC_2fWQA93W1AaAIYBPIqRBFCjDSZRVAJmaQIAE10complex128: %retptr"}
!65 = distinct !{!65, !"_ZN5numba7cpython7numbers16complex_abs_impl12_3clocals_3e11complex_absB3v14B42c8tJTC_2fWQA93W1AaAIYBPIqRBFCjDSZRVAJmaQIAE10complex128"}
!66 = !{!67, !69}
!67 = distinct !{!67, !68, !"_ZN5numba7cpython8mathimpl16hypot_float_impl12_3clocals_3e10hypot_implB3v15B42c8tJTC_2fWQA93W1AaAIYBPIqRBFCjDSZRVAJmaQIAEdd: %retptr"}
!68 = distinct !{!68, !"_ZN5numba7cpython8mathimpl16hypot_float_impl12_3clocals_3e10hypot_implB3v15B42c8tJTC_2fWQA93W1AaAIYBPIqRBFCjDSZRVAJmaQIAEdd"}
!69 = distinct !{!69, !70, !"_ZN5numba7cpython7numbers16complex_abs_impl12_3clocals_3e11complex_absB3v14B42c8tJTC_2fWQA93W1AaAIYBPIqRBFCjDSZRVAJmaQIAE10complex128: %retptr"}
!70 = distinct !{!70, !"_ZN5numba7cpython7numbers16complex_abs_impl12_3clocals_3e11complex_absB3v14B42c8tJTC_2fWQA93W1AaAIYBPIqRBFCjDSZRVAJmaQIAE10complex128"}
!71 = !{!72, !74}
!72 = distinct !{!72, !73, !"_ZN5numba7cpython8mathimpl16hypot_float_impl12_3clocals_3e10hypot_implB3v15B42c8tJTC_2fWQA93W1AaAIYBPIqRBFCjDSZRVAJmaQIAEdd: %retptr"}
!73 = distinct !{!73, !"_ZN5numba7cpython8mathimpl16hypot_float_impl12_3clocals_3e10hypot_implB3v15B42c8tJTC_2fWQA93W1AaAIYBPIqRBFCjDSZRVAJmaQIAEdd"}
!74 = distinct !{!74, !75, !"_ZN5numba7cpython7numbers16complex_abs_impl12_3clocals_3e11complex_absB3v14B42c8tJTC_2fWQA93W1AaAIYBPIqRBFCjDSZRVAJmaQIAE10complex128: %retptr"}
!75 = distinct !{!75, !"_ZN5numba7cpython7numbers16complex_abs_impl12_3clocals_3e11complex_absB3v14B42c8tJTC_2fWQA93W1AaAIYBPIqRBFCjDSZRVAJmaQIAE10complex128"}
!76 = !{!77, !79}
!77 = distinct !{!77, !78, !"_ZN5numba7cpython8mathimpl16hypot_float_impl12_3clocals_3e10hypot_implB3v15B42c8tJTC_2fWQA93W1AaAIYBPIqRBFCjDSZRVAJmaQIAEdd: %retptr"}
!78 = distinct !{!78, !"_ZN5numba7cpython8mathimpl16hypot_float_impl12_3clocals_3e10hypot_implB3v15B42c8tJTC_2fWQA93W1AaAIYBPIqRBFCjDSZRVAJmaQIAEdd"}
!79 = distinct !{!79, !80, !"_ZN5numba7cpython7numbers16complex_abs_impl12_3clocals_3e11complex_absB3v14B42c8tJTC_2fWQA93W1AaAIYBPIqRBFCjDSZRVAJmaQIAE10complex128: %retptr"}
!80 = distinct !{!80, !"_ZN5numba7cpython7numbers16complex_abs_impl12_3clocals_3e11complex_absB3v14B42c8tJTC_2fWQA93W1AaAIYBPIqRBFCjDSZRVAJmaQIAE10complex128"}
!81 = !{!82, !84}
!82 = distinct !{!82, !83, !"_ZN5numba7cpython8mathimpl16hypot_float_impl12_3clocals_3e10hypot_implB3v15B42c8tJTC_2fWQA93W1AaAIYBPIqRBFCjDSZRVAJmaQIAEdd: %retptr"}
!83 = distinct !{!83, !"_ZN5numba7cpython8mathimpl16hypot_float_impl12_3clocals_3e10hypot_implB3v15B42c8tJTC_2fWQA93W1AaAIYBPIqRBFCjDSZRVAJmaQIAEdd"}
!84 = distinct !{!84, !85, !"_ZN5numba7cpython7numbers16complex_abs_impl12_3clocals_3e11complex_absB3v14B42c8tJTC_2fWQA93W1AaAIYBPIqRBFCjDSZRVAJmaQIAE10complex128: %retptr"}
!85 = distinct !{!85, !"_ZN5numba7cpython7numbers16complex_abs_impl12_3clocals_3e11complex_absB3v14B42c8tJTC_2fWQA93W1AaAIYBPIqRBFCjDSZRVAJmaQIAE10complex128"}
