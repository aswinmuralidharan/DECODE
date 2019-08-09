from unittest import TestCase
import torch
import pytest
import matplotlib.pyplot as plt

import deepsmlm.test.utils_ci as tutil
from deepsmlm.generic.emitter import EmitterSet, CoordinateOnlyEmitter, RandomEmitterSet
from deepsmlm.generic.psf_kernel import DeltaPSF
from deepsmlm.neuralfitter.losscollection import OffsetROILoss
from deepsmlm.neuralfitter.pre_processing import ZasOneHot, OffsetRep, GlobalOffsetRep, ROIOffsetRep
from deepsmlm.generic.plotting.frame_coord import PlotFrame, PlotFrameCoord


def equal_nonzero(*a):
    """
    Test whether a and b have the same non-zero elements
    :param a: tensors
    :return: "torch.bool"
    """
    is_equal = torch.equal(a[0], a[0])
    for i in range(a.__len__() - 1):
        is_equal = is_equal * torch.equal(a[i].nonzero(), a[i + 1].nonzero())

    return is_equal


class TestZasMask(TestCase):
    def setUp(self) -> None:
        self.delta_psf = DeltaPSF(xextent=(-0.5, 31.5),
                                  yextent=(-0.5, 31.5),
                                  zextent=None,
                                  img_shape=(32, 32),
                                  dark_value=0.)

        self.zasmask = ZasOneHot(self.delta_psf, 5, 0.8)

    def test_forward(self):
        em = EmitterSet(torch.tensor([[15., 15., 100.]]),
                        torch.tensor([1.]),
                        frame_ix=torch.tensor([0]))
        img = self.zasmask.forward(em)
        self.assertAlmostEqual(1., img.max().item(), places=3, msg="Scaling is wrong.")


class TestDecodeRepresentation:

    @pytest.fixture(scope='class')
    def offset_rep(self):
        return OffsetRep((-0.5, 31.5), (-0.5, 31.5), None, (32, 32), cat_output=False)

    @pytest.fixture(scope='class')
    def em_set(self):
        num_emitter = 100
        return EmitterSet(torch.rand((num_emitter, 3)) * 40,
                          torch.rand(num_emitter),
                          torch.zeros(num_emitter))

    def test_forward_shape(self, offset_rep, em_set):

        p, I, x, y, z = offset_rep.forward(em_set)
        assert p.shape == I.shape, "Maps of Decode Rep. must have equal dimension."
        assert I.shape == x.shape, "Maps of Decode Rep. must have equal dimension."
        assert x.shape == y.shape, "Maps of Decode Rep. must have equal dimension."
        assert y.shape == z.shape, "Maps of Decode Rep. must have equal dimension."

    def test_forward_equal_nonzeroness(self, offset_rep, em_set):
        """
        Test whether the non-zero entries are the same in all channels.
        Note that this in principle stochastic but the chance of having random float exactly == 0 is super small.
        :return:
        """
        p, I, x, y, z = offset_rep.forward(em_set)
        assert equal_nonzero(p, I, x, y, z)

    def test_output_range(self, offset_rep, em_set):
        """
        Test whether delta x/y are between -0.5 and 0.5 (which they need to be for 1 coordinate unit == 1px
        :param offset_rep:
        :param em_set:
        :return:
        """
        p, I, dx, dy, z = offset_rep.forward(em_set)
        assert (dx <= 0.5).all(), "delta x/y must be between -0.5 and 0.5"
        assert (dx >= -0.5).all(), "delta x/y must be between -0.5 and 0.5"
        assert (dy <= 0.5).all(), "delta x/y must be between -0.5 and 0.5"
        assert (dy >= -0.5).all(), "delta x/y must be between -0.5 and 0.5"


class TestROIOffsetRep(TestDecodeRepresentation):

    @pytest.fixture(scope='class')
    def roi_offset(self):
        return ROIOffsetRep((-0.5, 31.5), (-0.5, 31.5), None, (32, 32))

    @pytest.fixture(scope='class')
    def em_set(self):
        """An easy emitter, two adjacent emitters, two overlaying emitters"""
        return CoordinateOnlyEmitter(torch.tensor([[14.9, 17.2, 300.],
                                                   [0., 0., 250.],
                                                   [1., 1., -250.],
                                                   [25., 25., 500.],
                                                   [25.2, 25.2, 700.],
                                                   [10., 10., 200.],
                                                   [11., 11., 500.]]))

    @pytest.fixture(scope='class')
    def loss(self):
        return OffsetROILoss(roi_size=3)

    def test_values(self, roi_offset, em_set, loss):
        target = roi_offset.forward(em_set)

        # plt.figure(figsize=(12, 8))
        # plt.subplot(231)
        # PlotFrame(target[0]).plot()
        # plt.subplot(232)
        # PlotFrame(target[1]).plot()
        # plt.subplot(234)
        # PlotFrame(target[2]).plot()
        # plt.subplot(235)
        # PlotFrame(target[3]).plot()
        # plt.subplot(236)
        # PlotFrame(target[4]).plot()
        # plt.show()

        """Test it together with the loss"""
        prediction = torch.rand((1, 5, 32, 32))
        loss_v = loss(prediction, target.unsqueeze(0))
        assert tutil.tens_almeq(loss_v[0, :, 1, 0], torch.zeros(5))
        assert tutil.tens_almeq(loss_v[0, :, 0, 1], torch.zeros(5))


class TestGlobalOffsetRep:

    @pytest.fixture(scope='class')
    def classyclassclass(self):
        return GlobalOffsetRep((-0.5, 31.5), (-0.5, 31.5), None, (32, 32))

    @pytest.fixture(scope='class')
    def two_em(self):
        return CoordinateOnlyEmitter(torch.tensor([[-0.5, 15.5, 0.], [31.5, 15.5, 0.]]))

    def test_forward_shape(self, classyclassclass, two_em):
        assert classyclassclass.assign_emitter(two_em).shape == torch.zeros(32, 32).shape

    def test_classification(self, classyclassclass, two_em):
        gt = torch.zeros(32, 32).type(torch.LongTensor)
        gt[16:, :] = 1

        prediction_ix = classyclassclass.assign_emitter(two_em)
        assert tutil.tens_almeq(gt, prediction_ix)

    # @pytest.mark.skip("Only for plotting.")
    def test_diag_em(self, classyclassclass):
        em = CoordinateOnlyEmitter(torch.tensor([[0., 0., 0.], [31., 31., 0.]]))
        prediction_ix = classyclassclass.assign_emitter(em)
        prediction_ix = prediction_ix.reshape(classyclassclass.img_shape[0], classyclassclass.img_shape[1])

        PlotFrame(prediction_ix).plot()
        plt.show()

        em = RandomEmitterSet(10, extent=32)
        ix_map = classyclassclass.assign_emitter(em)
        ix_map = ix_map.reshape(classyclassclass.img_shape[0], classyclassclass.img_shape[1])
        PlotFrameCoord(frame=ix_map, pos_tar=em.xyz).plot()
        plt.show()

        offset_maps = classyclassclass.forward(em)
        PlotFrameCoord(frame=offset_maps[2], pos_tar=em.xyz).plot()
        plt.show()

        PlotFrameCoord(frame=offset_maps[3], pos_tar=em.xyz).plot()
        plt.show()

        PlotFrameCoord(frame=offset_maps[4], pos_tar=em.xyz).plot()
        plt.show()
        assert True

    def test_mask(self, classyclassclass):
        classyclassclass.masked = True

        em = RandomEmitterSet(10, extent=32)
        em.phot = torch.randn_like(em.phot)
        offset_maps = classyclassclass.forward(em)
        PlotFrameCoord(frame=offset_maps[1], pos_tar=em.xyz).plot()
        plt.show()

        PlotFrameCoord(frame=offset_maps[2], pos_tar=em.xyz).plot()
        plt.show()

        PlotFrameCoord(frame=offset_maps[3], pos_tar=em.xyz).plot()
        plt.show()

        PlotFrameCoord(frame=offset_maps[4], pos_tar=em.xyz).plot()
        plt.show()
        assert True
